from PyQt5.uic import loadUiType
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from pathlib import Path
from shutil import copy
from glob import glob
import os, sys, time
from obspy.clients.fdsn import Client
from obspy import UTCDateTime as utc
from obspy import read_events, read_inventory
from obspy.core.event import Catalog
from obspy.clients.fdsn.mass_downloader import GlobalDomain, Restrictions, MassDownloader

import warnings
warnings.filterwarnings("ignore")

"""

A simple but powerfull GUI for using FDSNW services.

LogChange:
2021-05-09 > Initial.
2021-07-23 > Add some massages to statusbar.

Author: Saeed SoltaniMoghadam
Email1: saeed.soltanim@iiees.ac.ir
Email2: saeed.sltm@gmail.com

"""

# Load GUI template
ui,_ = loadUiType("fdsnw.ui")

# Define main class
class MainApp(QMainWindow, ui):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setupUi(self)
        self.setWindowTitle("FDSN-GUI")
        self.actionExit.triggered.connect(qApp.quit)
        self.actionReset.triggered.connect(self.resetItems)
        self.statusbar = self.statusBar()
        self.statusbar.showMessage("Ready")
        self.handdleExecuteButton()
        #========== Convert station format names
        self.stationFormats = {
            "CSS":"css",
            "KML":"kml",
            "SACPZ":"pz",
            "SHAPEFILE":"shp",
            "STATIONTXT":"txt",
            "STATIONXML":"xml"}
        #========== Convert catalog format names
        self.catalogFormats = {
            "CMTSOLUTION":"cmt",
            "CNV":"cnv",
            "JSON":"json",
            "KML":"kml",
            "NLLOC_OBS":"nobs",
            "NORDIC":"out",
            "QUAKEML":"xml",
            "SC3ML":"sc3ml",
            "SCARDEC":"sca",
            "SHAPEFILE":"shp",
            "ZMAP":"zmap"}
        #========== Convert waveform format names
        self.waveformFormat = {
            "GSE2":"gse",
            "MSEED":"msd",
            "PICKLE":"pickle",
            "SAC":"sac",
            "SACXY":"sacxy",
            "SEGY":"segy",
            "WAV":"wav"}
    
    # XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    # XXXXXXXXXXXXXXXXXXXXX Define Some Useful Functions XXXXXXXXXXXXXXXXXXXXXX
    # XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

    # Reset items in form
    def resetItems(self):
        '''
        Reset items in QT form to initial values.
        '''
        self.GB5_1_pushButton_1.setText("Load catalog file")
        self.GB5_2_pushButton_1.setText("Load station file")

    # Parse "placeholderText" or "text" to string from lineEdit
    def parseText(self, item):
        '''
        Parse "placeholderText" or "text" to string from lineEdit.
        '''
        obj = item.placeholderText()
        if item.text():
            obj = item.text()
        return obj

    # Parse Connection Setting Parameters
    def parsConnectionSetting(self):
        '''
        Parse Connection Setting Parameters received from user.
        '''
        self.URL = self.parseText(self.GB1_lineEdit_1)
        self.URL_List = self.GB1_comboBox_1.currentText()
        if self.URL_List != "Select from items":
            self.URL = self.URL_List.split()[1]
    
    # Convert Yes/No to Boolean
    def YesNo2Bool(self, str):
        '''
        Convert Yes/No to Boolean
        '''
        bool_dic = {
            "Yes": True,
            "No": False
        }
        return bool_dic[str]
    
    # Update statusBar information
    def updateStatusBar(self, string, timeout):
        '''
        Update statusBar massage
        '''
        self.statusbar.showMessage(string, timeout)

    # Save file name 
    def saveFile(self, name):
        '''
        Save file dialog, select file for saving. 
        '''
        if name == "GB6_pushButton_1":
            fileName, _ = QFileDialog.getSaveFileName(self, "Save station file", "", "All Files (*)")
            self.GB6_lineEdit_1.setText(fileName)
        if name == "GB6_pushButton_2":
            fileName, _ = QFileDialog.getSaveFileName(self, "Save catalog file", "", "All Files (*)")
            self.GB6_lineEdit_2.setText(fileName)
    
    # Open file name
    def openFile(self, name):
        '''
        Open file dialog, select file for opening. 
        '''
        if name == "GB5_1_pushButton_1":
            fileName, _ = QFileDialog.getOpenFileName(self,"Open catalog file", "","All Files (*)")
            self.localCatalog = self.readCatalog(fileName)
            if len(self.localCatalog):
                fileName = fileName.split(os.sep)[-1]
                self.GB5_1_pushButton_1.setText(fileName)
        if name == "GB5_2_pushButton_1":
            fileName, _ = QFileDialog.getOpenFileName(self,"Open station file", "","All Files (*)")
            self.localStation = self.readStation(fileName)
            if len(self.localStation):
                fileName = fileName.split(os.sep)[-1]
                self.GB5_2_pushButton_1.setText(fileName)

    # Open Folder
    def openFolder(self, name):
        '''
        Save folder dialog, select folder. 
        '''
        if name == "GB6_pushButton_3":
            folderName = QFileDialog.getExistingDirectory(self, "Select dolder to save waveform")
            self.GB6_lineEdit_3.setText(folderName)
    
    # Read catalog file
    def readCatalog(self, inpFile):
        '''
        Read catalog using obspy module, return obspy catalog object.
        '''
        try:
            cat = read_events(inpFile)
            self.updateStatusBar("%d event(s) found in catalog."%(len(cat)), 5000)
            return cat
        except:
            self.updateStatusBar("Can not read catalog format!", 5000)
            return Catalog()
    
    # Read station file
    def readStation(self, inpFile):
        '''
        Read station file using obspy module, return list of 'net.station' string.
        '''
        try:
            inv = read_inventory(inpFile)
            net_sta = [sta.split()[0] for sta in inv.get_contents()['stations']]
            self.updateStatusBar("%d station(s) found."%(len(net_sta)), 5000)
            return net_sta
        except:
            self.updateStatusBar("Can not read station file!", 5000)
            return []
    
    # Mass Downloader
    def massDownloader(self, chunkSize=86400, net="*", sta="*", loc="", cha="*"):
        '''
        Download continous waveform using obspy massDownloader.
        '''
        domain = GlobalDomain()
        folderName = self.startTime.strftime("%Y_%j_%H%M%S")
        restrictions = Restrictions(
            starttime=self.startTime,
            endtime=self.endTime,
            chunklength_in_sec=chunkSize,
            network=net, station=sta, location=loc, channel=cha,
            reject_channels_with_gaps=False,
            minimum_length=0.0)
        mdl = MassDownloader([self.URL])
        mdl.download(
            domain,
            restrictions,
            mseed_storage="Continous/%s/waveforms/%s"%(folderName, sta),
            stationxml_storage="Continous/%s/stations/%s"%(folderName, sta))
        
    # XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    # XXXXXXXXXXXXXXXXXXXXXXXXX End of This Section XXXXXXXXXXXXXXXXXXXXXXXXXXX
    # XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

    # Parse "Date and Time of Request" parameters
    def parseDateTime(self):
        '''
        Parse "Date and Time of Request" parameters.
        '''
        self.startTime = utc(self.GB2_dateTimeEdit_1.dateTime().toString("yyyy-MM-dd-hh:mm:ss"))
        self.endTime = utc(self.GB2_dateTimeEdit_2.dateTime().toString("yyyy-MM-dd-hh:mm:ss"))        

    # Parse "Station Request" parameters
    def parsStation(self):
        '''
        Parse "Station Request" parameters.
        '''
        self.latMinSt = float(self.parseText(self.GB3_lineEdit_1))
        self.latMaxSt = float(self.parseText(self.GB3_lineEdit_2))
        self.lonMinSt = float(self.parseText(self.GB3_lineEdit_3))
        self.lonMaxSt = float(self.parseText(self.GB3_lineEdit_4))
        self.levels = self.GB3_comboBox_1.currentText()
        self.netCodeSt = self.parseText(self.GB3_lineEdit_5)
        self.staCodeSt = self.parseText(self.GB3_lineEdit_6)
        self.locCodeSt = self.parseText(self.GB3_lineEdit_7)
        self.chaCodeST = self.parseText(self.GB3_lineEdit_8)

    # Parse "Catalog Request" parameters
    def parsCatalog(self):
        '''
        Parse "Catalog Request" parameters.
        '''
        self.latMinCa = float(self.parseText(self.GB4_lineEdit_1))
        self.latMaxCa = float(self.parseText(self.GB4_lineEdit_2))
        self.lonMinCa = float(self.parseText(self.GB4_lineEdit_3))
        self.lonMaxCa = float(self.parseText(self.GB4_lineEdit_4))
        self.depMin = float(self.parseText(self.GB4_lineEdit_5))
        self.depMax = float(self.parseText(self.GB4_lineEdit_6))
        self.magMin = float(self.parseText(self.GB4_lineEdit_7))
        self.magMax = float(self.parseText(self.GB4_lineEdit_8))
        self.incOrg = self.YesNo2Bool(self.GB4_comboBox_1.currentText())
        self.incMag = self.YesNo2Bool(self.GB4_comboBox_2.currentText())
        self.incAri = self.YesNo2Bool(self.GB4_comboBox_3.currentText())
    
    # Parse "Waveform Request" parameters
    def parsWaveform(self):
        '''
        Parse "Waveform Request" parameters.
        '''
        self.netCodeWa = self.parseText(self.GB5_lineEdit_1)
        self.staCodeWa = self.parseText(self.GB5_lineEdit_2)
        self.locCodeWa = self.parseText(self.GB5_lineEdit_3)
        self.chaCodeWa = self.parseText(self.GB5_lineEdit_4)
        self.atcRes = self.YesNo2Bool(self.GB5_comboBox_1.currentText())
        #========== Catalog-based mode
        self.timeBOT = float(self.parseText(self.GB5_1_lineEdit_1))
        self.timeAOT = float(self.parseText(self.GB5_1_lineEdit_2))
        #========== Continouse mode
        self.chunkSize = float(self.parseText(self.GB5_2_lineEdit_1))
        self.eComp = self.GB5_2_checkBox_1.isChecked()
        self.nComp = self.GB5_2_checkBox_2.isChecked()
        self.zComp = self.GB5_2_checkBox_3.isChecked()

    # Parse "Submit Request" parameters
    def parsSubmit(self):
        '''
        Parse "Submit Request" parameters.
        '''
        self.requestStation = self.GB6_checkBox_1.isChecked()
        self.requestCatalog = self.GB6_checkBox_2.isChecked()
        self.requestWaveform = self.GB6_checkBox_3.isChecked()
        self.stationPath = self.parseText(self.GB6_lineEdit_1)
        self.catalogPath = self.parseText(self.GB6_lineEdit_2)
        self.waveformPath = self.parseText(self.GB6_lineEdit_3)
    
    # Download Station Information
    def getStation(self):
        '''
        Download Station Information using FDSNW service.
        '''
        try:
            client = Client(self.URL)
        except:
            self.updateStatusBar("FDSNW service is not running!", 5000)
            return
        try:
            self.updateStatusBar("Fetching station metadata ...", 5000)
            inventory = client.get_stations(
                starttime=self.startTime,
                endtime=self.endTime,
                network=self.netCodeSt,
                station=self.staCodeSt,
                location=self.locCodeSt,
                channel=self.chaCodeST,
                minlatitude=self.latMinSt,
                maxlatitude=self.latMaxSt,
                minlongitude=self.lonMinSt,
                maxlongitude=self.lonMaxSt,
                level=self.levels)
            ReqFormat = self.GB6_comboBox_1.currentText()
            if self.GB6_comboBox_1.currentText() == "Format":
                ReqFormat = "STATIONXML"
            extention = self.stationPath.split(".")[-1]
            self.stationPath = self.stationPath.replace(extention, self.stationFormats[ReqFormat])
            inventory.write(self.stationPath, format=ReqFormat)
            self.updateStatusBar("Station metadata saved in '%s' file."%(self.stationPath), 5000)
        except:
            self.updateStatusBar("Operation failed! Please check your entries.", 5000)

    # Download Catalog Information
    def getCatalog(self):
        '''
        Download Catalog Information using FDSNW service.
        '''
        try:
            client = Client(self.URL)
        except:
            self.updateStatusBar("FDSNW service is not running!", 5000)
            return          
        try:
            self.updateStatusBar("Fetching catalog data ...", 5000)
            catalog = client.get_events(
                starttime=self.startTime,
                endtime=self.endTime,
                minlatitude=self.latMinCa,
                maxlatitude=self.latMaxCa,
                minlongitude=self.lonMinCa,
                maxlongitude=self.lonMaxCa,
                mindepth=self.depMin,
                maxdepth=self.depMax,
                minmagnitude=self.magMin,
                maxmagnitude=self.magMax,
                includeallorigins=self.incOrg,
                includeallmagnitudes=self.incMag,
                includearrivals=self.incAri)
            ReqFormat = self.GB6_comboBox_2.currentText()
            if self.GB6_comboBox_2.currentText() == "Format":
                ReqFormat = "QUAKEML"
            extention = self.catalogPath.split(".")[-1]
            self.catalogPath = self.catalogPath.replace(extention, self.catalogFormats[ReqFormat])
            catalog.write(self.catalogPath, format=ReqFormat)
            self.updateStatusBar("%d event(s) saved in catalog '%s' file."%(len(catalog), self.catalogPath), 5000)
        except:
            self.updateStatusBar("Operation failed! Please check your entries.", 5000)
    
    # Download Waveform Information
    def getWaveform(self):
        '''
        Download Waveform Information using FDSNW service.
        '''
        try:
            client = Client(self.URL)
        except:
            self.updateStatusBar("FDSNW service is not running!", 5000)
            return
        try:
            self.updateStatusBar("Fetching waveforms ...", 5000)
            stream = client.get_waveforms(
                starttime=self.startTime,
                endtime=self.endTime,
                network=self.netCodeWa,
                station=self.staCodeWa,
                location=self.locCodeWa,
                channel=self.chaCodeWa,
                attach_response=self.atcRes)
            saveDir = Path(self.waveformPath)
            saveDir.mkdir(parents=True, exist_ok=True)
            ReqFormat = self.GB6_comboBox_3.currentText()
            if self.GB6_comboBox_3.currentText() == "Format":
                ReqFormat = "MSEED"
            self.waveformSaveName = os.path.join(saveDir.name, "%s.%s"%(self.startTime.strftime("%Y_%j_%H%M%S"), self.waveformFormat[ReqFormat]))
            stream.write(self.waveformSaveName, format=ReqFormat)
            self.statusbar.showMessage("Waveforms saved in '%s' directory"%(self.waveformPath), 5000)
        except:
            self.updateStatusBar("Operation failed! Please check your entries.", 5000)

    # Download Catalog-based Waveform Information
    def getCatalogBasedWaveform(self):
        '''
        Use catalog data and download waveforms based on event's origin time.
        '''
        try:
            client = Client(self.URL)
        except:
            self.updateStatusBar("FDSNW service is not running!", 5000)
            return
        for event in self.localCatalog:
            try:
                if self.GB5_1_checkBox_2.isChecked():
                    self.staCodeWa = ",".join(sorted(set([pick.waveform_id.station_code for pick in event.picks])))
                OT = event.preferred_origin().time
                startTime = OT - self.timeBOT
                endTime = OT + self.timeAOT
                stream = client.get_waveforms(
                    starttime=startTime,
                    endtime=endTime,
                    network=self.netCodeWa,
                    station=self.staCodeWa,
                    location=self.locCodeWa,
                    channel=self.chaCodeWa,
                    attach_response=self.atcRes)
                saveDir = Path(self.waveformPath)
                saveDir.mkdir(parents=True, exist_ok=True)
                ReqFormat = self.GB6_comboBox_3.currentText()
                if self.GB6_comboBox_3.currentText() == "Format":
                    ReqFormat = "MSEED"
                self.waveformSaveName = os.path.join(saveDir.name, "%s.%s"%(OT.strftime("%Y_%j_%H%M%S"), self.waveformFormat[ReqFormat]))
                stream.write(self.waveformSaveName, format=ReqFormat)
                self.statusbar.showMessage("Waveforms saved in '%s' directory."%(self.waveformPath), 5000)
            except:
                self.updateStatusBar("Operation failed! Please check your entries.", 5000)
    
    # Download Continous Waveform Information
    def getContinousWaveform(self):
        '''
        Use station file and download continous waveforms.
        '''
        try:
            client = Client(self.URL)
        except:
            self.updateStatusBar("FDSNW service is not running!", 5000)
            return
        self.updateStatusBar("Fetching waveforms data ...", 5000)
        reqComponents = [self.GB5_2_checkBox_1.isChecked(), self.GB5_2_checkBox_2.isChecked(), self.GB5_2_checkBox_3.isChecked()]
        namComponents = ["??E", "??N", "??Z"]
        components = ",".join([v for k,v in zip(reqComponents, namComponents) if k])
        for i,netsta in enumerate(self.localStation):
            net, sta = netsta.split(".")
            self.massDownloader(self.chunkSize, net, sta, "", components)
            percentage = int((i+1)/len(self.localStation)*100)
            self.GB5_2_progressBar_1.setValue(percentage)
            self.GB5_2_progressBar_1.setFormat("Downloading . . . %p%")
        folderName = self.startTime.strftime("%Y_%j_%H%M%S")
        totalTraces = sum([len(files) for r, d, files in os.walk("Continous/%s/waveforms"%(folderName))])
        self.updateStatusBar("%d traces download successfully."%(totalTraces), 5000)

    # Execute "GetData!"
    def GetData(self):
        self.parsConnectionSetting()
        self.parseDateTime()
        self.parsSubmit()
        if self.requestStation:
            self.parsStation()
            self.getStation()
        if self.requestCatalog:
            self.parsCatalog()
            self.getCatalog()
        if self.requestWaveform:
            self.parsWaveform()
            if self.GB5_1_pushButton_1.text() != "Load catalog file":
                self.getCatalogBasedWaveform()
            elif self.GB5_2_pushButton_1.text() != "Load station file":
                self.getContinousWaveform()
            else:
                self.getWaveform()

    # Handdle button
    def handdleExecuteButton(self):
        self.GB6_pushButton_4.clicked.connect(self.GetData)
        self.GB6_pushButton_1.clicked.connect(lambda: self.saveFile(self.GB6_pushButton_1.objectName()))
        self.GB6_pushButton_2.clicked.connect(lambda: self.saveFile(self.GB6_pushButton_2.objectName()))
        self.GB6_pushButton_3.clicked.connect(lambda: self.openFolder(self.GB6_pushButton_3.objectName()))
        self.GB5_1_pushButton_1.clicked.connect(lambda: self.openFile(self.GB5_1_pushButton_1.objectName()))
        self.GB5_2_pushButton_1.clicked.connect(lambda: self.openFile(self.GB5_2_pushButton_1.objectName()))

# Main App
def main():
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    app.exec_()

if __name__ == "__main__":
    main()
