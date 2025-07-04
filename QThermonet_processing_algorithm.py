# -*- coding: utf-8 -*-

"""
/***************************************************************************
 QThermonet
                                 A QGIS plugin
 This plugin links QGIS to pythermonet
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-12-05
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
__date__ = '2024-12-05'
__copyright__ = '(C) 2024 by Jane Lund Andersen/VIA University College'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
import inspect
from qgis.PyQt.QtGui import QIcon

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessingAlgorithm,
                       QgsProcessingException,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterString)

# from thermonet.dimensioning.thermonet_classes import Brine, Thermonet, BHEconfig, aggregatedLoad
# from thermonet.dimensioning.dimensioning_functions import print_project_id, read_dimensioned_topology, read_aggregated_load, run_sourcedimensioning, print_source_dimensions

class QThermonetAlgorithm(QgsProcessingAlgorithm):
    """
    This algorithm runs the pythermonet code for selected inputs

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    PID="PID"
    OUTPUT = 'OUTPUT'
    INPUT_A = 'INPUT_A'
    INPUT_Topology = 'INPUT_Topology'
    # INPUT_Brine = 'INPUT_Brine'
    INPUT_Thermonet = 'INPUT_Thermonet'
    HE_MODE = "HE_MODE"
    rhoBrine = "rhoBrine"
    cBrine = "cBrine"
    muBrine = "muBrine"
    lBrine = "lBrine"

    def initAlgorithm(self, config=None):
        """
        Define the parameters for the algorithm.
        """
        # Project name
        self.addParameter(
            QgsProcessingParameterString(
                self.PID,
                "Project name:"
            )
        )
        
        # Input file for specifying aggregated load for heating
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_A,
                self.tr("Input aggregated load file:"),
                extension="dat"  # Restrict selection to dat files
            )
        )
        
        # Input file containing topology information
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_Topology,
                self.tr("Input topology file:"),
                extension="dat"  # Restrict selection to dat files
            )
        )
        
        # # Input file containing brine information
        # self.addParameter(
        #     QgsProcessingParameterFile(
        #         self.INPUT_Brine,
        #         self.tr("Input brine file:"),
        #         extension="dat"  # Restrict selection to dat files
        #     )
        # )
        
        # Input file containing thermonet information
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_Thermonet,
                self.tr("Input thermonet file:"),
                extension="dat"  # Restrict selection to dat files
            )
        )
        
        # Add a dropdown menu parameter
        self.addParameter(
            QgsProcessingParameterEnum(
                self.HE_MODE,
                description="Select heat exchanger source mode",
                options=["BHE", "HHE"],  # Options for the dropdown menu
                defaultValue=0  # Default selection index (0 corresponds to "BHE")
            )
        )
        
        # Input numerical values for brine density
        self.addParameter(
            QgsProcessingParameterNumber(
                self.rhoBrine,
                "Brine density (kg/m3), T = 0C",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=965,
                minValue=0
            )
        )
        
        # Input numerical values for brine specific heat
        self.addParameter(
            QgsProcessingParameterNumber(
                self.cBrine,
                "Brine specific heat (J/kg/K)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=4450,
                minValue=0
            )
        )
        
        # Input numerical values for brine dynamic viscosity
        self.addParameter(
            QgsProcessingParameterNumber(
                self.muBrine,
                "Brine dynamic viscosity (Pa*s)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=5e-3,
                minValue=0
            )
        )
        
        # Input numerical values for brine thermal conductivity 
        self.addParameter(
            QgsProcessingParameterNumber(
                self.lBrine,
                "Brine thermal conductivity (W/m/K)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.45,
                minValue=0.0
            )
        )
        
        # Output file
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                "Output File",
                "CSV files (*.csv)"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        output_path = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        
        #Handle input layers
        feedback.pushInfo("Checking input layers...")
        agg_load_file = self.parameterAsFile(parameters, self.INPUT_A, context)
        if not agg_load_file:
            raise QgsProcessingException("Invalid aggregated load input file!")
            
        topology_file = self.parameterAsFile(parameters, self.INPUT_Topology, context)
        if not topology_file:
            raise QgsProcessingException("Invalid topology input file!")
            
        # brine_file = self.parameterAsFile(parameters, self.INPUT_Brine, context)
        # if not brine_file:
        #     raise QgsProcessingException("Invalid brine input file!")
            
        thermonet_file = self.parameterAsFile(parameters, self.INPUT_Thermonet, context)
        if not thermonet_file:
            raise QgsProcessingException("Invalid thermonet input file!")
        
        # # Set brine properties
        # feedback.pushInfo("Setting brine properties...")
        # brine = Brine(rho=self.rhoBrine, c=self.cBrine, mu=self.muBrine, l=self.lBrine)
        
        # # Initialise thermonet object
        # feedback.pushInfo("Initializing thermonet object...")
        # net = Thermonet(D_gridpipes=0.3, l_p=0.4, l_s_H=1.25, l_s_C=1.25, rhoc_s=2.5e6, z_grid=1.2, T0 = 9.03, A = 7.90)
        # # Read remaining data from user specified file
        # net, pipeGroupNames = read_dimensioned_topology(net, brine, TOPO_file)  
        
        # # Initialise aggregated load object
        # feedback.pushInfo("Initializing aggregated load object...")
        # aggLoad = aggregatedLoad(Ti_H = -3, Ti_C = 20, f_peak=1, t_peak=4)
        # # Read remaining data from user specified file
        # aggLoad = read_aggregated_load(aggLoad, brine, agg_load_file)  
        
        # # Heat source (either BHE or HHE)
        # feedback.pushInfo("Setting heat source configuration...")
        # if self.HE_MODE is "BHE":
        #     source_config = BHEconfig(q_geo = 0.0185, r_b=0.152/2, r_p=0.02, SDR=11, l_ss=2.36, rhoc_ss=2.65e6, l_g=1.75, rhoc_g=3e6, D_pipes=0.015, NX=1, D_x=15, NY=6, D_y=15)
        # else:
        #     source_config = HHEconfig(N_HHE=6, d=0.04, SDR=17, D=1.5)
            
        # # Dimensioning of sources - results printed to console
        # feedback.pushInfo("Dimensioning sources...")
        # source_config = run_sourcedimensioning(brine, net, aggLoad, source_config)
        # print_project_id(PID)
        # print_source_dimensions(source_config,net)
        
        # # Write to output file
        # feedback.pushInfo("Writing output...")
        # with open(output_path, "w", newline="") as csv_file:
        #     writer = csv.writer(csv_file)
        #     writer.writerows(table_content)

        # feedback.pushInfo("Processing complete!")
        
        return {self.OUTPUT: output_path}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Dimension sources'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Dimensioning'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
    
    def icon(self):
        cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]
        icon = QIcon(os.path.join(os.path.join(cmd_folder, 'logo.png')))
        return icon
    
    def shortHelpString(self):
        """
        Return a short help string for the algorithm.
        """
        return "This algorithm performs source dimensioning of a thermonet by \
            calling pythermonet with the input files. It stores the results in\
                an output file."

    def createInstance(self):
        return QThermonetAlgorithm()
