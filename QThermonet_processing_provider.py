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

from qgis.core import QgsProcessingProvider
# from .GetBuildings_processing_algorithm import GetBuildingsAlgorithm
from .GetBuildingsAndBBR_processing_algorithm import GetBuildingsAndBBRAlgorithm
from .LoadCalculation_processing_algorithm import LoadCalculationAlgorithm
from .ToggleThermonet_processing_algorithm import ToggleThermonetAlgorithm
# from .AggregatedLoad_processing_algorithm import AggregatedLoadAlgorithm
from .ServicePipes_processing_algorithm import ServicePipesAlgorithm
from .PipeHierarchy_processing_algorithm import PipeHierarchyAlgorithm
from .PipeTopology_processing_algorithm import PipeTopologyAlgorithm
# from .QThermonet_processing_algorithm import QThermonetAlgorithm
from .FullDimensioning_processing_algorithm import FullDimensioningAlgorithm
# from .Test_processing_algorithm import TestAlgorithm


class QThermonetProvider(QgsProcessingProvider):

    def __init__(self):
        """
        Default constructor.
        """
        QgsProcessingProvider.__init__(self)

    def unload(self):
        """
        Unloads the provider. Any tear-down steps required by the provider
        should be implemented here.
        """
        pass

    def loadAlgorithms(self):
        """
        Loads all algorithms belonging to this provider.
        """
        # self.addAlgorithm(GetBuildingsAlgorithm())
        self.addAlgorithm(GetBuildingsAndBBRAlgorithm())
        self.addAlgorithm(ToggleThermonetAlgorithm())
        self.addAlgorithm(LoadCalculationAlgorithm())
        # self.addAlgorithm(AggregatedLoadAlgorithm())
        self.addAlgorithm(ServicePipesAlgorithm())
        self.addAlgorithm(PipeHierarchyAlgorithm())
        self.addAlgorithm(PipeTopologyAlgorithm())
        self.addAlgorithm(FullDimensioningAlgorithm())
        # self.addAlgorithm(TestAlgorithm())
        # self.addAlgorithm(QThermonetAlgorithm())
    
    def id(self):
        """
        Returns the unique provider id, used for identifying the provider. This
        string should be a unique, short, character only string, eg "qgis" or
        "gdal". This string should not be localised.
        """
        return 'QThermonet'

    def name(self):
        """
        Returns the provider name, which is used to describe the provider
        within the GUI.

        This string should be short (e.g. "Lastools") and localised.
        """
        return self.tr('QThermonet')

    def icon(self):
        cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]
        icon = QIcon(os.path.join(os.path.join(cmd_folder, 'logo.png')))
        return icon

    def longName(self):
        """
        Returns the a longer version of the provider name, which can include
        extra details such as version numbers. E.g. "Lastools LIDAR tools
        (version 2.2.1)". This string should be localised. The default
        implementation returns the same string as name().
        """
        return self.name()
