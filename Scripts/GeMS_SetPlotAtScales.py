# sets PlotAtScale values for a point eature class

# September 2017: now invokes edit session before setting values (line 135)

# June 2019: updated to work with Python 3 in ArcGIS Pro.
# Ran script through 2to3. Only incidental debugging required after.
# November 2021: reordered linew 9-14

import arcpy, os.path, sys
from GeMS_utilityFunctions import *

versionString = "GeMS_SetPlotAtScales.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_SetPlotAtScales.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

# global dictionaries
OPTypeDict = {}
OPLCMDict = {}
OPOCDDict = {}

#############################


def plotScale(separation, minSeparationMapUnits):
    return int(round(separation / minSeparationMapUnits))


def makeDictsOP(inFc):
    fields = [
        "OBJECTID",
        "Type",
        "LocationConfidenceMeters",
        "OrientationConfidenceDegrees",
    ]
    with arcpy.da.SearchCursor(inFc, fields) as cursor:
        for row in cursor:
            OPTypeDict[row[0]] = row[1]
            OPLCMDict[row[0]] = row[2]
            OPOCDDict[row[0]] = row[3]


def lessSignificantOP(fid1, fid2):
    if OPTypeDict[fid1] != OPTypeDict[fid2]:
        # if one is overturned or upright and other is not
        if (
            "upright" in OPTypeDict[fid1].lower()
            or "overturned" in OPTypeDict[fid1].lower()
        ) and not (
            "upright" in OPTypeDict[fid2].lower()
            or "overturned" in OPTypeDict[fid2].lower()
        ):
            return fid2
        elif (
            "upright" in OPTypeDict[fid2].lower()
            or "overturned" in OPTypeDict[fid2].lower()
        ) and not (
            "upright" in OPTypeDict[fid1].lower()
            or "overturned" in OPTypeDict[fid1].lower()
        ):
            return fid1
        # if one is bedding and one is not
        elif (
            "bedding" in OPTypeDict[fid1].lower()
            and not "bedding" in OPTypeDict[fid2].lower()
        ):
            return fid2
        elif (
            "bedding" in OPTypeDict[fid2].lower()
            and not "bedding" in OPTypeDict[fid1].lower()
        ):
            return fid1
    else:
        # if one has better OrientationConfidenceDegrees
        if OPOCDDict[fid1] < OPOCDDict[fid2]:
            return fid2
        elif OPOCDDict[fid2] < OPOCDDict[fid1]:
            return fid1
        else:
            return fid1


##############################
# args
#   inFc = featureClass
#   minSeparation (in mm on map)
#   maxPlotAtScale  = 500000

inFc = arcpy.GetParameterAsText(0)
minSeparation_mm = float(arcpy.GetParameterAsText(1))
maxPlotAtScale = float(arcpy.GetParameterAsText(2))
input_mapname = arcpy.GetParameterAsText(3)

addMsgAndPrint(versionString)

# test for valid input:
# inFc exists and has item PlotAtScale
if not arcpy.Exists(inFc):
    forceExit()
if arcpy.Describe(inFc).shapeType != 'Point':
    addMsgAndPrint("Feature class is not a Point type")
    forceExit()

gdb = os.path.dirname(inFc)
if arcpy.Describe(gdb).dataType == "FeatureDataset":
    gdb = os.path.dirname(gdb)
if getGDBType(gdb) == 'FileGDB':
    inFcLayer = inFc
elif getGDBType(gdb) == 'EGDB':
    inFcLayer = arcpy.management.SelectLayerByAttribute(inFc, where_clause="MapName = '" + input_mapname + "'")
    
fields = arcpy.ListFields(inFcLayer)
fieldNames = []
for field in fields:
    fieldNames.append(field.name)
if not "PlotAtScale" in fieldNames:
    arcpy.AddField_management(inFcLayer, "PlotAtScale", "FLOAT")
    addMsgAndPrint("Adding field PlotAtScale to {}".format(inFcLayer))

if os.path.basename(inFc) == "OrientationPoints":
    addMsgAndPrint("Populating OrientationPointsDicts")
    makeDictsOP(inFc)
    isOP = True
else:
    isOP = False

if getGDBType(gdb) == 'FileGDB':
    outTable = gdb + "/xxxPlotAtScales"
elif getGDBType(gdb) == 'EGDB':
    outTable = arcpy.env.scratchWorkspace + "/xxxPlotAtScales"    
testAndDelete(outTable)
mapUnits = "meters"
minSeparationMapUnits = minSeparation_mm / 1000.0
searchRadius = minSeparationMapUnits * maxPlotAtScale
if not "meter" in arcpy.Describe(inFcLayer).spatialReference.linearUnitName.lower():
    # units are feet of some flavor
    mapUnits = "feet"
    searchRadius = searchRadius * 3.2808
    minSeparationMapUnits = minSeparationMapUnits * 3.2808
addMsgAndPrint("Search radius is " + str(searchRadius) + " " + mapUnits)
addMsgAndPrint("Building near table")
arcpy.PointDistance_analysis(inFcLayer, inFcLayer, outTable, searchRadius)

inPoints = []
outPointDict = {}

# read outTable into Python list inPoints, with each list component = [distance, fid1, fid2]
fields = ["DISTANCE", "INPUT_FID", "NEAR_FID"]
with arcpy.da.SearchCursor(outTable, fields) as cursor:
    for row in cursor:
        inPoints.append([row[0], row[1], row[2]])
addMsgAndPrint("   " + str(len(inPoints)) + " rows in initial near table")

# step through inPoints, smallest distance first, and write list of FID, PlotAtScale (outPoints)
addMsgAndPrint("   Sorting through near table and calculating PlotAtScale values")
inPoints.sort()
lastLenInPoints = 0
while len(inPoints) > 1 and lastLenInPoints != len(inPoints):
    lastLenInPoints = len(inPoints)
    pointSep = inPoints[0][0]
    if isOP:  # figure out the most significant point
        pt = lessSignificantOP(inPoints[0][1], inPoints[0][2])
    else:  # take the second point
        pt = inPoints[0][2]
    outPointDict[pt] = plotScale(pointSep, minSeparationMapUnits)
    inPoints.remove(inPoints[0])
    j = len(inPoints)
    for i in range(1, j + 1):
        # addMsgAndPrint(str(i)+', '+str(j))
        aPt = inPoints[j - i]
        if aPt[1] == pt or aPt[2] == pt:
            inPoints.remove(aPt)
            # addMsgAndPrint( 'removing '+str(aPt))
    addMsgAndPrint("   # inPoints = " + str(len(inPoints)))

for i in range(0, len(inPoints)):
    addMsgAndPrint("      " + str(inPoints[i]))


# attach plotScale values from outPoints to inFcLayer
addMsgAndPrint("Updating " + os.path.basename(inFc))
edit = arcpy.da.Editor(gdb)
edit.startEditing(False, True)
edit.startOperation()
fields = ["OBJECTID", "PlotAtScale"]
with arcpy.da.UpdateCursor(inFcLayer, fields) as cursor:
    for row in cursor:
        if row[0] in list(outPointDict.keys()):
            row[1] = outPointDict[row[0]]
        else:
            row[1] = maxPlotAtScale
        cursor.updateRow(row)
edit.stopOperation()
edit.stopEditing(True)
    
# get rid of xxxPlotAtScales
addMsgAndPrint("Deleting " + outTable)
testAndDelete(outTable)





#-------------------validation script----------
import arcpy, os
sys.path.insert(1, os.path.join(os.path.dirname(__file__),'Scripts'))
from GeMS_utilityFunctions import *
class ToolValidator:
  # Class to add custom behavior and properties to the tool and tool parameters.

    def __init__(self):
        # set self.params for use in other function
        self.params = arcpy.GetParameterInfo()

    def initializeParameters(self):
        # Customize parameter properties. 
        # This gets called when the tool is opened.
        self.params[3].enabled = False 
        return

    def updateParameters(self):
        # Modify parameter values and properties.
        # This gets called each time a parameter is modified, before 
        # standard validation.
        fds = os.path.dirname(self.params[0].valueAsText)
        gdb = os.path.dirname(fds)
        if getGDBType(gdb) == 'FileGDB':
            self.params[3].enabled = False
        elif getGDBType(gdb) == 'EGDB':
            self.params[3].enabled = True    

            db_schema = os.path.basename(fds).split('.')[0] + '.' + os.path.basename(fds).split('.')[1]
            mapList = []
            for row in arcpy.da.SearchCursor(gdb + '\\' + db_schema + '.Domain_MapName',['code']):
                mapList.append(row[0])
            self.params[3].filter.list = sorted(set(mapList))          
        return

    def updateMessages(self):
        # Customize messages for the parameters.
        # This gets called after standard validation.
        return

    # def isLicensed(self):
    #     # set tool isLicensed.
    # return True