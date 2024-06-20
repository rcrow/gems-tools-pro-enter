# GeMS_InclinationNumbers_AGP2.py
# Creates a point feature class called OrientationPointLabels with dip and plunge
# number labels for appropriate features within OrientationPoints. The location
# of the label is offset based on characteristics of the rotated symbol and the map scale.

# Adds the new annotation feature class to your map composition.

# If this script fails because of locking issues, try (a) Stop Editing, or (b)
# save any edits and save the map composition, exit ArcMap, and restart ArcMap.
# Maybe this script will then run satisfactorily.

# Create 17 October 2017 by Ralph Haugerud
# Edits 21 May 2019 by Evan Thoms:
#   Upgraded to work with Python 3 and ArcGIS Pro 2
#   Ran script through 2to3 to find and fix simple syntactical differences
#   Manually debugged remaining issues mostly to do with to with methods
#   which are no longer available in arcpy.

import arcpy, os.path, sys, math, shutil, pathlib
from GeMS_utilityFunctions import *

versionString = "GeMS_InclinationNumbers.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_InclinationNumbers.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

debug = False


#########Stuff for placing dip/plunge numbers########
def showInclination(oType):
    if "horizontal" in oType.lower() or "vertical" in oType.lower() or len(oType) < 2:
        return False
    else:
        return True


#####################################################
addMsgAndPrint("  " + versionString)

# get inputs
inFds = arcpy.GetParameterAsText(0)
mapScale = float(arcpy.GetParameterAsText(1))
input_mapname = arcpy.GetParameterAsText(2)

gdb = os.path.dirname(inFds)
db_schema = ''
if getGDBType(gdb) == 'EGDB':
    db_schema = os.path.basename(inFds).split('.')[0] + '.' + os.path.basename(inFds).split('.')[1] + '.'
   
if "GeologicMap" not in os.path.basename(inFds):
    addMsgAndPrint("Not GeologicMap feature class, OrientationPointLabels not (re)created.")
    forceExit()

OPfc = os.path.join(gdb, db_schema + "GeologicMap", db_schema + 'OrientationPoints')
if not arcpy.Exists(OPfc):
    addMsgAndPrint("  Geodatabase {} lacks feature class OrientationPoints.".format(os.path.basename(gdb)))
    forceExit()

desc = arcpy.Describe(OPfc)
mapUnits = desc.spatialReference.linearUnitName
if "meter" in mapUnits.lower():
    mapUnitsPerMM = mapScale / 1000.0
else:
    mapUnitsPerMM = mapScale / 1000.0 * 3.2808

if numberOfRows(OPfc) == 0:
    addMsgAndPrint("  0 rows in OrientationPoints.")
    forceExit()

## MAKE ORIENTATIONPOINTLABELS FEATURE CLASS or delete existing features from EGDB feature class by MapName
arcpy.env.workspace = os.path.join(gdb, db_schema + "GeologicMap")
OPL = os.path.join(gdb, db_schema + "GeologicMap", db_schema + 'OrientationPointLabels')
if getGDBType(gdb) == 'FileGDB':
    testAndDelete(OPL)
    arcpy.CreateFeatureclass_management(inFds, "OrientationPointLabels", "POINT")
    arcpy.AddField_management(OPL, "OrientationPointsID", "TEXT", "", "", 50)
    arcpy.AddField_management(OPL, "Inclination", "TEXT", "", "", 3)
    arcpy.AddField_management(OPL, "PlotAtScale", "FLOAT")    
if getGDBType(gdb) == 'EGDB':
    arcpy.management.MakeFeatureLayer(OPL, 'del_layer', "MapName = '" + input_mapname + "'")
    arcpy.management.DeleteRows('del_layer')

## ADD FEATURES FOR ROWS IN ORIENTATIONPOINTS WITHOUT 'HORIZONTAL' OR 'VERTICAL' IN THE TYPE VALUE
OPfields = [
    "SHAPE@XY",
    "OrientationPoints_ID",
    "Type",
    "Azimuth",
    "Inclination",
    "PlotAtScale",
]
if getGDBType(gdb) == 'FileGDB':
    whereclause = "OBJECTID > 0"
elif getGDBType(gdb) == 'EGDB':
    whereclause = "MapName = '" + input_mapname + "'"
attitudes = arcpy.da.SearchCursor(OPfc, OPfields, where_clause=whereclause)

if gdb[-4:] == ".gdb":
    OPLfields = ["SHAPE@XY", "OrientationPointsID", "Inclination", "PlotAtScale"]
    inclinLabels = arcpy.da.InsertCursor(OPL, OPLfields)
elif getGDBType(gdb) == 'EGDB':
    edit = arcpy.da.Editor(gdb)
    edit.startEditing(False, True)
    OPLfields = ["SHAPE@XY", "OrientationPointsID", "Inclination", "PlotAtScale", "MapName"]
    inclinLabels = arcpy.da.InsertCursor(OPL, OPLfields)
    edit.startOperation()
    
for row in attitudes:
    oType = row[2]
    if showInclination(oType):
        x = row[0][0]
        y = row[0][1]
        OP_ID = row[1]
        azi = row[3]
        inc = int(round(row[4]))
        paScale = row[5]
        if isPlanar(oType):
            geom = " S "
            inclinRadius = 2.4 * mapUnitsPerMM
            azir = math.radians(azi)
        else:  # assume linear
            geom = " L "
            inclinRadius = 7.4 * mapUnitsPerMM
            azir = math.radians(azi - 90)
        ix = x + math.cos(azir) * inclinRadius
        iy = y - math.sin(azir) * inclinRadius

        addMsgAndPrint("    inserting " + oType + geom + str(int(round(azi))) + "/" + str(inc))
        if gdb[-4:] == ".gdb": 
            inclinLabels.insertRow(([ix, iy], OP_ID, inc, paScale))
        elif getGDBType(gdb) == 'EGDB': 
            inclinLabels.insertRow(([ix, iy], OP_ID, inc, paScale, input_mapname))

if getGDBType(gdb) == 'EGDB': 
    edit.stopOperation()
    edit.stopEditing(True)
    
del inclinLabels
del attitudes

# add default layer file to map and repoint the datasource
scripts_folder = pathlib.Path(__file__).parent.resolve()
lyrx_path = os.path.join(os.path.dirname(scripts_folder), "Resources", "OrientationPointsLabels.lyrx")

aprx = arcpy.mp.ArcGISProject("CURRENT")
m = aprx.listMaps(aprx.activeMap.name)[0]
objRefLayer = m.listLayers()[0]
objLayerFile = arcpy.mp.LayerFile(lyrx_path)
m.insertLayer(objRefLayer, objLayerFile, "BEFORE")
objAddedLayer = m.listLayers()[0]

current_workspace = objAddedLayer.connectionProperties["connection_info"]["database"]
objAddedLayer.updateConnectionProperties(current_workspace,gdb, False, True)

defQuery = "PlotAtScale" + " >= " + str(mapScale) 
objAddedLayer.definitionQuery = defQuery

# set the map layer to the correct OrientationPointsLabels if there is more than one in the enterprise geodatabase under different schemas
if getGDBType(gdb) == 'EGDB':
    newcp = objAddedLayer.connectionProperties
    newcp['dataset'] = db_schema + 'OrientationPointLabels'
    objAddedLayer.updateConnectionProperties(objAddedLayer.connectionProperties["dataset"],newcp, False, True)



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
        self.params[2].enabled = False
        return

    def updateParameters(self):
        # Modify parameter values and properties.
        # This gets called each time a parameter is modified, before 
        # standard validation.
        gdb = os.path.dirname(self.params[0].valueAsText)
        arcpy.env.workspace = gdb
        if getGDBType(gdb) == 'EGDB':
            db_schema = os.path.basename(self.params[0].valueAsText).split('.')[0] + '.' + os.path.basename(self.params[0].valueAsText).split('.')[1]
            if len(arcpy.ListTables(db_schema + '.Domain_MapName')) == 1:
                self.params[2].enabled = True    
                mapList = []
                for row in arcpy.da.SearchCursor(gdb + '\\' + db_schema + '.Domain_MapName',['code']):
                    mapList.append(row[0])
                self.params[2].filter.list = sorted(set(mapList))         
            else:
                self.params[2].enabled = False
                self.params[2].value = None
        else:
            self.params[2].enabled = False
            self.params[2].value = None
        return

    def updateMessages(self):
        # Customize messages for the parameters.
        # This gets called after standard validation.
        return

    # def isLicensed(self):
    #     # set tool isLicensed.
    # return True
