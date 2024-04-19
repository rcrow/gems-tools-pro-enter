# MapOutline.py
#   generates rectangular (in lat-long) map outline and
#   appropriate tics in projection of user's choosing. Result is
#   stored in an existing geodatabase
#
#   For complex map outlines, try several runs and intersect the results.
#
# Ralph Haugerud, U.S. Geological Survey
#   rhaugerud@usgs.gov
#
# July 23, 2019: updated to work with Python 3 in ArcGIS Pro 2
#  Only had to make some syntax edits.
#  Renamed from mapOutline_Arc10.py to mapOutline_AGP2.py
#  Evan Thoms

# April 2024: tool rewritten to eliminate need for temporary feature classes, tables, files, and scratch workspace
#  All intermidiate processing done with in-memory objects instead.
#  Added support for enterprise geodatabases.
#  Christian Halsted

import arcpy, sys, os
from GeMS_utilityFunctions import *

versionString = "GeMS_MapOutline.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/usgs/gems-tools-pro/master/Scripts/GeMS_MapOutline.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

"""
INPUTS
maxLongStr  # in D M S, separated by spaces. Decimals OK.
            #   Note that west values must be negative
            #   -122.625 = -122 37 30
            #   if value contains spaces it should be quoted
minLatStr   # DITTO
dLong       # in decimal degrees OR decimal minutes
            #   values <= 5 are assumed to be degrees
            #   values  > 5 are assumed to be minutes
dLat        # DITTO
            # default values of dLong and dLat are 7.5
ticInterval # in decimal minutes! Default value is 2.5
isNAD27     # NAD27 or NAD83 for lat-long locations
outgdb      # existing geodatabase to host output feature classes
outSpRef    # output spatial reference system
scratch     # scratch folder, must be writable
"""

c = ","
degreeSymbol = "°"
minuteSymbol = "'"
secondSymbol = '"'


def addMsgAndPrint(msg, severity=0):
    # prints msg to screen and adds msg to the geoprocessor (in case this is run as a tool)
    # print msg
    try:
        for string in msg.split("\n"):
            # Add appropriate geoprocessing message
            if severity == 0:
                arcpy.AddMessage(string)
            elif severity == 1:
                arcpy.AddWarning(string)
            elif severity == 2:
                arcpy.AddError(string)
    except:
        pass


def dmsStringToDD(dmsString):
    dms = dmsString.split()
    dd = abs(float(dms[0]))
    if len(dms) > 1:
        dd = dd + float(dms[1]) / 60.0
    if len(dms) > 2:
        dd = dd + float(dms[2]) / 3600.0
    if dms[0][0] == "-":
        dd = 0 - dd
    return dd


def ddToDmsString(dd):
    dd = abs(dd)
    degrees = int(dd)
    minutes = int((dd - degrees) * 60)
    seconds = int(round((dd - degrees - (minutes / 60.0)) * 3600))
    if seconds == 60:
        minutes = minutes + 1
        seconds = 0
    dmsString = str(degrees) + degreeSymbol
    dmsString = dmsString + str(minutes) + minuteSymbol
    if seconds != 0:
        dmsString = dmsString + str(seconds) + secondSymbol
    return dmsString


addMsgAndPrint(versionString)

## MAP BOUNDARY
# get and check inputs
SELongStr = arcpy.GetParameterAsText(0)
SELatStr = arcpy.GetParameterAsText(1)
dLong = float(arcpy.GetParameterAsText(2))
dLat = float(arcpy.GetParameterAsText(3))
ticInterval = float(arcpy.GetParameterAsText(4))
if arcpy.GetParameterAsText(5) == "true":
    isNAD27 = True
else:
    isNAD27 = False

if isNAD27:
    xycs = arcpy.SpatialReference(4267) #xycs = 'GEOGCS["GCS_North_American_1927",DATUM["D_North_American_1927",SPHEROID["Clarke_1866",6378206.4,294.9786982]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433],AUTHORITY["EPSG",4267]]'
else:
    xycs = arcpy.SpatialReference(4269) #xycs = 'GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433],AUTHORITY["EPSG",4269]]'
    
outgdb = arcpy.GetParameterAsText(6)
input_schema = arcpy.GetParameterAsText(7)
input_mapname = arcpy.GetParameterAsText(8)
outSpRef = arcpy.GetParameterAsText(9)

# set workspace
arcpy.env.workspace = outgdb

# calculate maxLong and minLat, dLat, dLong, minLong, maxLat
maxLong = dmsStringToDD(SELongStr)
minLat = dmsStringToDD(SELatStr)
if dLong > 5:
    dLong = dLong / 60.0
if dLat > 5:
    dLat = dLat / 60.0
minLong = maxLong - dLong
maxLat = minLat + dLat

# test for and delete any feature classes to be created
for fc in ["MapOutline", "MapTics"]:
    if arcpy.Exists(fc) and outgdb[-4:] == ".gdb":
        arcpy.Delete_management(fc)
        addMsgAndPrint("  deleted feature class {}".format(fc))
    elif arcpy.Exists(fc) and outgdb[-4:] == ".sde":    
        arcpy.management.MakeFeatureLayer(outgdb + '\\' + input_schema + '.' + fc, 'del_layer', "MapName = '" + input_mapname + "'")
        arcpy.management.DeleteRows('del_layer')

## MAP OUTLINE
addMsgAndPrint("  writing map outline feature")
sr = arcpy.SpatialReference(text=outSpRef)
if outgdb[-4:] == ".gdb":
    arcpy.management.CreateFeatureclass(outgdb, 'MapOutline', "POLYLINE", None, "DISABLED", "DISABLED", sr, '', 0, 0, 0, '')
    
array = arcpy.Array([arcpy.Point(minLong, maxLat),
                     arcpy.Point(maxLong, maxLat),
                     arcpy.Point(maxLong, minLat),
                     arcpy.Point(minLong, minLat),
                     arcpy.Point(minLong, maxLat)])
#spatial_reference = arcpy.SpatialReference(4326)
polyline = arcpy.Polyline(array, xycs)

if isNAD27:
    geotransformation = arcpy.ListTransformations (xycs, sr)[0] #"NAD_1927_To_NAD_1983_NADCON"
else:
    geotransformation = None # "WGS_1984_(ITRF00)_To_NAD_1983"

polyline_projected = polyline.projectAs(sr, geotransformation)
arcpy.edit.Densify(polyline_projected, "DISTANCE", "1 Meters")
if outgdb[-4:] == ".gdb":
    cursor = arcpy.da.InsertCursor(outgdb + '\MapOutline', ["SHAPE@"])
    cursor.insertRow([polyline_projected])
elif outgdb[-4:] == ".sde":
    edit = arcpy.da.Editor(outgdb)
    edit.startEditing(False, True)
    edit.startOperation()
    cursor = arcpy.da.InsertCursor(outgdb + '\\' + input_schema + '.MapOutline', ["SHAPE@","MapName"])    
    cursor.insertRow([polyline_projected, input_mapname])
    edit.stopOperation()
    edit.stopEditing(True)

## TICS  
addMsgAndPrint("  writing tic features")
ticInterval = ticInterval / 60.0  # convert minutes to degrees
ticList = []  #ID,LONGITUDE,LATITUDE
nTic = 1
for y in range(0, int(dLat / ticInterval) + 1):
    ticLat = (y * ticInterval) + minLat
    for x in range(0, int(dLong / ticInterval) + 1):
        ticLong = (x * ticInterval) + minLong
        ticList.append([nTic, ticLong, ticLat])
        nTic = nTic + 1
# addMsgAndPrint(str(ticList))

if outgdb[-4:] == ".gdb":
    arcpy.management.CreateFeatureclass(outgdb, 'MapTics', "POINT", None, "DISABLED", "DISABLED", sr, '', 0, 0, 0, '')
    arcpy.management.AddField(outgdb + '\MapTics', "ID", "LONG", None, None, None, "ID", "NULLABLE", "NON_REQUIRED", '')
    # add attributes
    for fld in ["Easting", "Northing"]:
        arcpy.AddField_management(outgdb + '\MapTics', fld, "DOUBLE")
    for fld in ["LatDMS", "LongDMS"]:
        arcpy.AddField_management(outgdb + '\MapTics', fld, "TEXT", "", "", 20)
    cursor = arcpy.da.InsertCursor(outgdb + '\MapTics', ["SHAPE@","ID","LatDMS","LongDMS","Easting","Northing"])    
elif outgdb[-4:] == ".sde":
    edit = arcpy.da.Editor(outgdb)
    edit.startEditing(False, True)
    cursor = arcpy.da.InsertCursor(outgdb + '\\' + input_schema + '.' + 'MapTics', ["SHAPE@","ID","LatDMS","LongDMS","Easting","Northing","MapName"])
    edit.startOperation()
    
for tic in ticList:
    point = arcpy.Point(tic[1], tic[2])
    point_geometry = arcpy.PointGeometry(point,xycs)
    point_projected = point_geometry.projectAs(sr, geotransformation)
    if outgdb[-4:] == ".gdb":
        cursor.insertRow([point_projected, tic[0], ddToDmsString(tic[1]), ddToDmsString(tic[2]), point_projected.firstPoint.X, point_projected.firstPoint.Y])
    if outgdb[-4:] == ".sde":
        cursor.insertRow([point_projected, tic[0], ddToDmsString(tic[1]), ddToDmsString(tic[2]), point_projected.firstPoint.X, point_projected.firstPoint.Y, input_mapname])
        
if outgdb[-4:] == ".sde":
    edit.stopOperation()
    edit.stopEditing(True)



#-------------------validation script----------
class ToolValidator:
  # Class to add custom behavior and properties to the tool and tool parameters.

    def __init__(self):
        # set self.params for use in other function
        self.params = arcpy.GetParameterInfo()

    def initializeParameters(self):
        # Customize parameter properties. 
        # This gets called when the tool is opened.
        self.params[7].enabled = False
        self.params[8].enabled = False           
        return

    def updateParameters(self):
        # Modify parameter values and properties.
        # This gets called each time a parameter is modified, before 
        # standard validation.
        gdb = self.params[6].valueAsText
        if gdb[-4:] == '.gdb':
            self.params[7].enabled = False
            self.params[8].enabled = False
        elif gdb[-4:] == '.sde':
            self.params[7].enabled = True    
            self.params[8].enabled = True 

            schemaList = []
            arcpy.env.workspace = gdb  
            datasets = arcpy.ListDatasets("*GeologicMap*", "Feature")	
            for dataset in datasets:
                schemaList.append(dataset.split('.')[0] + '.' + dataset.split('.')[1])
            self.params[7].filter.list = sorted(set(schemaList))	

            if self.params[7].value is not None:
                mapList = []
                for row in arcpy.da.SearchCursor(gdb + '\\' + self.params[7].value + '.Domain_MapName',['code']):
                    mapList.append(row[0])
                self.params[8].filter.list = sorted(set(mapList))         
        return

    def updateMessages(self):
        # Customize messages for the parameters.
        # This gets called after standard validation.
        return

    # def isLicensed(self):
    #     # set tool isLicensed.
    # return True