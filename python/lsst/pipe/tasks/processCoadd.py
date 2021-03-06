#!/usr/bin/env python
#
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#

import lsst.pex.config as pexConfig
import lsst.pipe.base as pipeBase
import lsst.daf.base as dafBase
import lsst.afw.table as afwTable
import lsst.afw.math as afwMath
from .coaddBase import CoaddArgumentParser
from .processImage import ProcessImageTask

class ProcessCoaddConfig(ProcessImageTask.ConfigClass):
    """Config for ProcessCoadd"""
    coaddName = pexConfig.Field(
        doc = "coadd name: typically one of deep or goodSeeing",
        dtype = str,
        default = "deep",
    )
    doScaleVariance = pexConfig.Field(dtype=bool, default=True, doc = "Scale variance plane using empirical noise")

class ProcessCoaddTask(ProcessImageTask):
    """Process a Coadd image
    
    """
    ConfigClass = ProcessCoaddConfig
    _DefaultName = "processCoadd"

    def __init__(self, **kwargs):
        ProcessImageTask.__init__(self, **kwargs)
        self.dataPrefix = self.config.coaddName + "Coadd_"

    @pipeBase.timeMethod
    def scaleVariance(self, exposure):
        ctrl = afwMath.StatisticsControl()
        ctrl.setAndMask(~0x0)
        var    = exposure.getMaskedImage().getVariance()
        mask   = exposure.getMaskedImage().getMask()
        dstats = afwMath.makeStatistics(exposure.getMaskedImage(), afwMath.VARIANCECLIP, ctrl).getValue(afwMath.VARIANCECLIP)
        vstats = afwMath.makeStatistics(var, mask, afwMath.MEANCLIP, ctrl).getValue(afwMath.MEANCLIP)
        vrat   = dstats / vstats
        self.log.info("Renormalising variance by %f" % (vrat))
        var   *= vrat

    def makeIdFactory(self, dataRef):
        expBits = dataRef.get(self.config.coaddName + "CoaddId_bits")
        expId = long(dataRef.get(self.config.coaddName + "CoaddId"))
        return afwTable.IdFactory.makeSource(expId, 64 - expBits)
        

    @pipeBase.timeMethod
    def run(self, dataRef):
        """Process a coadd image
        
        @param dataRef: butler data reference corresponding to coadd patch
        @return pipe_base Struct containing these fields:
        - exposure: calibrated exposure (calexp): as computed if config.doCalibrate,
            else as upersisted and updated if config.doDetection, else None
        - calib: object returned by calibration process if config.doCalibrate, else None
        - apCorr: aperture correction: as computed config.doCalibrate, else as unpersisted
            if config.doMeasure, else None
        - sources: detected source if config.doDetection, else None
        """
        self.log.info("Processing %s" % (dataRef.dataId))

        # initialize outputs
        coadd = None

        if self.config.doCalibrate:
            coadd = dataRef.get(self.config.coaddName + "Coadd")
            if dataRef.datasetExists(self.dataPrefix + "initPsf"):
                initPsf = dataRef.get(self.dataPrefix + "initPsf")
                coadd.setPsf(initPsf)
            else:
                self.log.warn("Could not load initial PSF; dataset does not exist")
            if self.config.doScaleVariance:
                self.scaleVariance(coadd)

        # delegate most of the work to ProcessImageTask
        result = self.process(dataRef, coadd)
        result.coadd = coadd
        return result

    @classmethod
    def _makeArgumentParser(cls):
        return CoaddArgumentParser(name=cls._DefaultName, datasetType="deepCoadd")

    def _getConfigName(self):
        """Return the name of the config dataset
        """
        return "%s_processCoadd_config" % (self.config.coaddName,)
    
    def _getMetadataName(self):
        """Return the name of the metadata dataset
        """
        return "%s_processCoadd_metadata" % (self.config.coaddName,)
