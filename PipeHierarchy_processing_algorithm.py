# -*- coding: utf-8 -*-

"""
/***************************************************************************
 QThermonet
                                 A QGIS plugin
 This plugin links QGIS to pythermonet
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2025-06-10
        copyright            : (C) 2024 by Jane Lund Andersen/VIA University College
        email                : jana@via.dk
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Jane Lund Andersen/VIA University College'
__date__ = '2025-06-10'
__copyright__ = '(C) 2025 by Jane Lund Andersen/VIA University College'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
import inspect
from collections import deque
from qgis import processing
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication 
from PyQt5.QtCore import QVariant
from qgis.core import (
                       QgsCoordinateTransform, 
                       QgsCoordinateReferenceSystem,
                       QgsExpression,
                       QgsExpressionContext,
                       QgsExpressionContextUtils,
                       QgsField,
                       QgsLineSymbol,
                       QgsProcessing, 
                       QgsProcessingAlgorithm,
                       QgsProcessingException,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingParameterVectorLayer,
                       QgsProject,
                       QgsSingleSymbolRenderer,
                       QgsVectorFileWriter,
                       QgsVectorLayer
                       )

class PipeHierarchyAlgorithm(QgsProcessingAlgorithm):
    
    #Handle input/output
    PIPES_LAYER = "PIPES_LAYER"
    SOURCE_LAYER = "SOURCE_LAYER" 
    OUTPUT = "OUTPUT"

    
    def initAlgorithm(self, config=None):
        #1st input

        param = QgsProcessingParameterVectorLayer(
                self.PIPES_LAYER,
                "Select the main pipes Layer",
                [QgsProcessing.TypeVectorLine],
            )
        
        param.setHelp(
            "The input pipes layer must:\n"
            "- include the main pipes of the thermonet"
            "- Use a compatible CRS (preferably WGS84/EPSG:3857)."
        )

        self.addParameter(param)

        
        #2nd input
        param = QgsProcessingParameterFeatureSource(
                self.SOURCE_LAYER,
                "Select the thermonet source area Layer",
                [QgsProcessing.TypeVectorPolygon],
            )
        param.setHelp(
            "The input source area layer must:\n"
            "- consist of a single polygon in a shapefile/geojson format"
            "- Use a compatible CRS (preferably WGS84/EPSG:3857)."
            "The source area layer outlines the location of the BHE/HHE field"
        )

        self.addParameter(param)
        
        #output
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                self.tr('Output GeoJSON'),
                fileFilter="GeoJSON (*.geojson)"  # Filter for file type
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        
        input_pipes_layer = self.parameterAsVectorLayer(parameters, self.PIPES_LAYER, context)
        input_source_layer = self.parameterAsVectorLayer(parameters, self.SOURCE_LAYER, context)
        output_path = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        
        ## Step 0: Re-project layers if necessarty (units should be meters for algorithm to work)
        default_projected_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        def is_geographic(crs):
            return crs.isGeographic()
        
        # Use the projected CRS of the input if it's already projected
        if is_geographic(input_pipes_layer.crs()):
            feedback.pushInfo(f"Pipes layer is in geographic CRS ({input_pipes_layer.crs().authid()}), reprojecting to {default_projected_crs.authid()}")
            pipes_layer_proj = processing.run(
                "native:reprojectlayer",
                {
                    'INPUT': input_pipes_layer,
                    'TARGET_CRS': default_projected_crs,
                    'OUTPUT': 'memory:'
                },
                context=context,
                feedback=feedback
            )['OUTPUT']
        else:
            feedback.pushInfo(f"Pipes layer is already projected: {input_pipes_layer.crs().authid()}")
            pipes_layer_proj = input_pipes_layer
        
        # Do the same for source layer
        if is_geographic(input_source_layer.crs()):
            feedback.pushInfo(f"Source layer is in geographic CRS ({input_source_layer.crs().authid()}), reprojecting to {pipes_layer_proj.crs().authid()}")
            source_layer_proj = processing.run(
                "native:reprojectlayer",
                {
                    'INPUT': input_source_layer,
                    'TARGET_CRS': pipes_layer_proj.crs(),  # ensure it matches pipes
                    'OUTPUT': 'memory:'
                },
                context=context,
                feedback=feedback
            )['OUTPUT']
        else:
            feedback.pushInfo(f"Source layer is already projected: {input_source_layer.crs().authid()}")
            source_layer_proj = input_source_layer

        
        ## Step 1: Dissolve pipes layer and add to new output layer
        dissolved_pipes = processing.run(
            "native:dissolve",
            {
                'INPUT': pipes_layer_proj,  # Input pipes layer
                'FIELD': [],  # Empty list = dissolve all features into one
                'OUTPUT': 'memory:'  # Use memory layer for temporary result
            },
            context=context,
            feedback=feedback
        )                
        dissolved_pipes_layer = dissolved_pipes['OUTPUT']
        
        
        # Step 2: Split the pipes into segments at junctions
        split_pipes = processing.run(
            "native:splitwithlines",
            {
                'INPUT': dissolved_pipes_layer,
                'LINES': dissolved_pipes_layer,
                'OUTPUT': 'memory:'
            },
            context=context,
            feedback=feedback
        )                
        split_pipes_layer = split_pipes['OUTPUT']
        
        
        # Step 3: Calculate lengths of pipe segments
        provider = split_pipes_layer.dataProvider()

        field_name = "ellip_length"
        if field_name not in [field.name() for field in split_pipes_layer.fields()]:
            provider.addAttributes([QgsField(field_name, QVariant.Double)])
            split_pipes_layer.updateFields()
        
        # Prepare the $length expression
        expression = QgsExpression('$length')
        expr_context = QgsExpressionContext()
        expr_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(split_pipes_layer))
        
        updated_features = {}
        
        for feature in split_pipes_layer.getFeatures():
            expr_context.setFeature(feature)  # Set the feature for evaluation
            ellip_length = expression.evaluate(expr_context)  # Compute length
            ellip_length = round(ellip_length, 1)
        
            if expression.hasEvalError():
                feedback.pushInfo(f"Feature {feature.id()} - ERROR: {expression.evalErrorString()}")
                continue
        
            updated_features[feature.id()] = {provider.fieldNameIndex(field_name): ellip_length}
        
        # Apply changes
        if updated_features:
            provider.changeAttributeValues(updated_features)
            split_pipes_layer.updateFields()
            split_pipes_layer.updateExtents()
            feedback.pushInfo("Ellipsoidal lengths added successfully!")
        else:
            feedback.pushInfo("Warning: No valid geometries found.")
        
        
        # # Step 4: Find main pipe and recursively assign levels
        root_pipe_id = self.find_closest_pipe(split_pipes_layer, source_layer_proj, context)

        if root_pipe_id is not None:
            feedback.pushInfo(f"Root pipe assigned with level 0 (Feature ID: {root_pipe_id})")
        else:
            feedback.reportError("No valid root pipe found!", fatalError=False)
        
        feedback.pushInfo("Building pipe network and assigning levels...")
        # Ensure 'Level' field exists before assigning values
        level_field_name = "Level"
        if level_field_name not in [field.name() for field in split_pipes_layer.fields()]:
            split_pipes_layer.dataProvider().addAttributes([QgsField(level_field_name, QVariant.Int)])
            split_pipes_layer.updateFields()
            
        # Set all levels to -1 to clearly mark unvisited
        level_idx = split_pipes_layer.fields().indexOf("Level")
        initial_levels = {f.id(): {level_idx: -1} for f in split_pipes_layer.getFeatures()}
        split_pipes_layer.dataProvider().changeAttributeValues(initial_levels)

        self.assign_levels(split_pipes_layer, root_pipe_id, feedback)
        feedback.pushInfo("Level assignment completed.")

        
        # Step 5: Dissolve pipe features based on level
        expr_context = QgsExpressionContext()
        pipes_dissolved_on_level = processing.run(
            "native:dissolve", 
            {
                'INPUT':split_pipes_layer,
                'FIELD': ['Level'],
                'SEPARATE_DISJOINT': True,
                'OUTPUT': 'memory:'
             }
            )
        pipes_layer = pipes_dissolved_on_level['OUTPUT']
        
        
        ## Step 6: Recalculate trace lengths
        provider = pipes_layer.dataProvider()

        field_name = "ellip_length"
        if field_name not in [field.name() for field in pipes_layer.fields()]:
            provider.addAttributes([QgsField(field_name, QVariant.Double)])
            pipes_layer.updateFields()
        
        # Prepare the $length expression
        expression = QgsExpression('$length')
        expr_context = QgsExpressionContext()
        expr_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(pipes_layer))
        
        updated_features = {}
        
        for feature in pipes_layer.getFeatures():
            expr_context.setFeature(feature)  # Set the feature for evaluation
            ellip_length = expression.evaluate(expr_context)  # Compute length
            ellip_length = round(ellip_length, 1)
        
            if expression.hasEvalError():
                feedback.pushInfo(f"Feature {feature.id()} - ERROR: {expression.evalErrorString()}")
                continue
        
            updated_features[feature.id()] = {provider.fieldNameIndex(field_name): ellip_length}
        
        # Apply changes
        if updated_features:
            provider.changeAttributeValues(updated_features)
            pipes_layer.updateFields()
            pipes_layer.updateExtents()
            feedback.pushInfo("Ellipsoidal lengths added successfully!")
        else:
            feedback.pushInfo("Warning: No valid geometries found.")
        
        
        ## Step 7: Reproject and export the pipes layer and add to map
        output_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        
        pipes_layer_wgs84 = processing.run(
            "native:reprojectlayer",
            {
                'INPUT': pipes_layer,
                'TARGET_CRS': output_crs,
                'OUTPUT': 'memory:'
            },
            context=context,
            feedback=feedback
        )['OUTPUT']

        error = QgsVectorFileWriter.writeAsVectorFormat(
            pipes_layer_wgs84,
            output_path,
            "UTF-8",
            pipes_layer_wgs84.crs(),
            "GeoJSON"
        )
        
        error_code = error[0] if isinstance(error, tuple) else error
    
        if error_code == QgsVectorFileWriter.NoError:                    
            feedback.pushInfo(f"Layer successfully exported to {output_path}")
        else:
            feedback.pushInfo(f"Failed to export the layer. Error code: {error}")
    
        # Load your dissolved pipes layer
        layer_name = os.path.splitext(os.path.basename(output_path))[0]
        layer = QgsVectorLayer(output_path, layer_name, "ogr")
        if not layer.isValid():
            raise QgsProcessingException("Could not load the output layer!")
        QgsProject.instance().addMapLayer(layer)
        
        # Dynamic symbology, (not functioning)
        # # Define dynamic width parameters:
        # min_width = 0.25  # thinner for high Level values
        # max_width = 1.5   # thicker for low Level values
        
        # # Create a basic line symbol.
        # symbol = QgsLineSymbol.createSimple({})
        
        # # Build the expression for dynamic width.
        # # This expression scales the "Level" field so that:
        # # - minimum("Level") results in max_width (thicker line)
        # # - maximum("Level") results in min_width (thinner line)
        # width_expr = 'scale_linear("Level", minimum("Level"), maximum("Level"), {maxw}, {minw})'.format(
        #     maxw=max_width, minw=min_width
        # )
        
        # # Get the symbol layer (assuming the first one) and set its data-defined width.
        # symbol_layer = symbol.symbolLayer(0)
        # try:
        #     # Preferred: using the enum for width.
        #     symbol_layer.setDataDefinedProperty(QgsSymbolLayer.PropertyWidth, QgsProperty.fromExpression(width_expr))
        # except Exception as e:
        #     # If that fails (e.g., due to version differences), try using the string key "width".
        #     symbol_layer.setDataDefinedProperty("width", QgsProperty.fromExpression(width_expr))

        # # Apply the symbol to a single symbol renderer and set it on the layer.
        # renderer = QgsSingleSymbolRenderer(symbol)
        # layer.setRenderer(renderer)

        line_symbol = QgsLineSymbol.createSimple({ # Create the main line symbol
            'color': 'black',  # Line color
            'width': '1.1',  # Line width
        })
        layer.setRenderer(QgsSingleSymbolRenderer(line_symbol))
        layer.triggerRepaint() # Refresh the layer to apply the changes
    
        ## Finish up
        feedback.pushInfo("Processing completed successfully.")
        return {
            self.OUTPUT: output_path
            }
    
    def find_closest_pipe(self, split_pipes_layer, source_layer_proj, context):
        """Finds the closest pipe segment to the input polygon and assigns level 0."""
        
        # Get CRS of split_pipes_layer (assumes all features in the same CRS)
        layer_crs = split_pipes_layer.crs()
        source_layer_crs = source_layer_proj.crs()
        
        # Create a coordinate transform if needed
        if layer_crs != source_layer_crs:
            transform = QgsCoordinateTransform(source_layer_crs, layer_crs, QgsProject.instance())
        else:
            transform = None
    
        # Get the input polygon geometry (assuming a single feature)
        source_feature = next(source_layer_proj.getFeatures(), None)
        if not source_feature:
            return None  # No source polygon found
        
        source_geom = source_feature.geometry()
        
        # Transform input geometry if needed
        if transform:
            source_geom.transform(transform)
    
        min_distance = float("inf")
        closest_feature_id = None
    
        # Find the closest pipe segment
        for feature in split_pipes_layer.getFeatures():
            pipe_geom = feature.geometry()
            distance = source_geom.distance(pipe_geom)
            if distance < min_distance:
                min_distance = distance
                closest_feature_id = feature.id()
    
        # Update the level attribute of the closest segment
        if closest_feature_id is not None:
            return closest_feature_id  # Return the ID of the root pipe
    
        return None
    
    def assign_levels(self, split_pipes_layer, root_pipe_id, feedback):
        """
        (Debug version) Assign levels with BFS, but log every step so we can see
        why two disjoint pipes end up at Level 0.
        """
    
        graph = self.build_network_graph(split_pipes_layer)  # your existing graph (buffer=1 m)
        features = {f.id(): f for f in split_pipes_layer.getFeatures()}  # id → QgsFeature
    
        # Get the 'Level' field index
        level_idx = split_pipes_layer.fields().indexOf("Level")
        if level_idx == -1:
            feedback.reportError("The 'Level' field was not found.", fatalError=True)
            return
    
        if root_pipe_id not in graph:
            feedback.reportError(f"Root pipe ID {root_pipe_id} not in graph.", fatalError=True)
            return
    
        # 1) Log the entire adjacency list for the root, before BFS even starts
        neighs_of_root = graph.get(root_pipe_id, [])
        feedback.pushInfo(
            f"[DEBUG] Root {root_pipe_id} has neighbors: {neighs_of_root}"
        )
    
        # Dictionary to store {feature_id: assigned_level}
        level_assignments = {}
        level_assignments[root_pipe_id] = 0
    
        queue = deque([root_pipe_id])
    
        while queue:
            parent_id = queue.popleft()
            parent_level = level_assignments[parent_id]
    
            # 2) Log which parent we are processing
            feedback.pushInfo(
                f"[DEBUG] Processing parent_id={parent_id} at Level={parent_level}"
            )
    
            # 3) Get all neighbors of this parent
            all_neighbors = graph.get(parent_id, [])
            feedback.pushInfo(
                f"[DEBUG]   All neighbors of {parent_id}: {all_neighbors}"
            )
    
            # 4) Filter out those that already have a level
            unassigned = [nid for nid in all_neighbors if nid not in level_assignments]
            feedback.pushInfo(f"[DEBUG]   Unassigned neighbors: {unassigned}")
    
            if not unassigned:
                feedback.pushInfo("[DEBUG]   → No unassigned neighbors, skipping.")
                continue
    
            # 5) Sort unassigned by descending ellip_length
            #    We'll log each one's length so you see why a given ID is “longest.”
            lengths = {}
            for nid in unassigned:
                val = features[nid].attribute("ellip_length")
                lengths[nid] = val
            feedback.pushInfo(f"[DEBUG]   Their ellip_lengths: {lengths}")
    
            sorted_neighbors = sorted(
                unassigned,
                key=lambda nid: features[nid].attribute("ellip_length"),
                reverse=True
            )
            feedback.pushInfo(
                f"[DEBUG]   Sorted (longest first): {sorted_neighbors}"
            )
    
            # 6) Assign levels: longest → same level, others → parent_level+1
            best = sorted_neighbors[0]
            level_assignments[best] = parent_level
            feedback.pushInfo(
                f"[DEBUG]   → Assigning feature {best} Level={parent_level}"
            )
    
            for other_nid in sorted_neighbors[1:]:
                level_assignments[other_nid] = parent_level + 1
                feedback.pushInfo(
                    f"[DEBUG]   → Assigning feature {other_nid} Level={parent_level + 1}"
                )
    
            # 7) Enqueue all sorted_neighbors, so they get processed in turn
            queue.extend(sorted_neighbors)
    
        # 8) After BFS, log exactly which features ended up with which Level
        for fid, lvl in sorted(level_assignments.items()):
            feedback.pushInfo(f"[RESULT] Feature {fid} → Level {lvl}")
    
        # 9) Push these values back into the layer
        attr_updates = {fid: {level_idx: lvl} for fid, lvl in level_assignments.items()}
        split_pipes_layer.dataProvider().changeAttributeValues(attr_updates)
    
        # 10) Warn if some pipes never got assigned (i.e. disconnected sub-trees)
        total = sum(1 for _ in split_pipes_layer.getFeatures())
        if len(level_assignments) != total:
            feedback.reportError(
                f"[WARNING] Only {len(level_assignments)} of {total} segments got a level. "
                "Check for disconnected pieces."
            )

    def build_network_graph(self, split_pipes_layer):
        """Build the network graph by considering segments within 1 meter."""
        graph = {}
        for feature in split_pipes_layer.getFeatures():
            connected_segments = self.find_connected_segments_within_distance(split_pipes_layer, feature)
            graph[feature.id()] = connected_segments
        return graph
    
    def find_connected_segments_within_distance(self, split_pipes_layer, feature, distance=1.0):
        """Find all connected segments within a given distance from the current feature."""
        input_geometry = feature.geometry()
        buffer_geometry = input_geometry.buffer(distance, segments=5)  # Buffer around the feature
        
        connected_segments = []
        for other_feature in split_pipes_layer.getFeatures():
            if feature.id() != other_feature.id() and buffer_geometry.intersects(other_feature.geometry()):
                connected_segments.append(other_feature.id())
        
        return connected_segments
  
    def name(self):
        return 'Optional: Pipe hierarchy'

    def displayName(self):
        return self.tr(self.name())

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return '2. Thermonet'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def icon(self):
        cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]
        return QIcon(os.path.join(cmd_folder, 'logo6-pipes-simple.png'))

    def shortHelpString(self):
        return ("<p><b> This tool: </b></p>"
                "<p> - constructs a pipe network hierarchy for a thermonet "
                "based on an input pipe layer with the geometry of the main pipes, "
                "and the location of the thermonet source area for the HHE/BHE field.</p>"
                "<p>Note that the pipe input layer needs to be in a tree structure"
                " (i.e. no circular loops, and all pipes touching (or within 1 "
                "m of) at least one other pipe).</p>"
                "<p>The source area file is a polygon that is located closest to "
                "the main pipe of the network, the size of the source area is "
                "not important.</p>"
        )
    
    def createInstance(self):
        return PipeHierarchyAlgorithm()

