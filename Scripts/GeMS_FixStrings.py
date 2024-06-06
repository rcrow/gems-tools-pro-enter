#   Script to clean up string fields in a GeMS database
##      Removes leading and trailing spaces
##      Converts "<null>", "" and similar to <null> (system nulls).
#       Ralph Haugerud, 28 July 2020
#       Updated to Python 3, 8/20/21 and added to toolbox, Evan Thoms

import arcpy, os, os.path, sys
from GeMS_utilityFunctions import *

versionString = "GeMS_FixStrings.py, version of 10/5/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_FixStrings.py"
checkVersion(versionString, rawurl, "gems-tools-pro")


def fixTableStrings(fc, ws, whereclause):
    # addMsgAndPrint(f'fc: {fc} :: ws: {ws}')
    fields1 = arcpy.ListFields(os.path.join(ws,fc), "", "String")
    fields = ["OBJECTID"]
    for f in fields1:
        fields.append(f.name)
    if getGDBType(ws) == 'EGDB' and 'MapName' not in fields:
        #addMsgAndPrint('..not processed')
        return
    edit = arcpy.da.Editor(ws)
    edit.startEditing(False, True)
    edit.startOperation()    
    with arcpy.da.UpdateCursor(os.path.join(ws,fc), fields, where_clause = whereclause) as cursor:
        for row in cursor:
            trash = ""
            updateRowFlag = False
            row1 = [row[0]]
            for f in row[1:]:
                updateFieldFlag = False
                f0 = f
                if f != None:
                    if f != f.strip():
                        f = f.strip()
                        updateFieldFlag = True
                    if f.lower() == "<null>" or f == "":
                        f = None
                        updateFieldFlag = True
                    if updateFieldFlag:
                        updateRowFlag = True
                row1.append(f)
            if updateRowFlag:
                try:
                    addMsgAndPrint(str(row1))
                    cursor.updateRow(row1)
                except Exception as error:
                    addMsgAndPrint(f"\u200B  Row {str(row[0])}. {error}")
    edit.stopOperation()
    edit.stopEditing(True)


#########################

gdb = arcpy.GetParameterAsText(0)
input_schema = arcpy.GetParameterAsText(1)
input_mapname = arcpy.GetParameterAsText(2)

addMsgAndPrint(versionString)
arcpy.env.workspace = gdb

if getGDBType(gdb) == 'FileGDB':
    whereclause = "OBJECTID > 0"
elif getGDBType(gdb) == 'EGDB':
    whereclause = "MapName = '" + input_mapname + "'"
    
tables = arcpy.ListTables(input_schema + '*')
for tb in tables:
    addMsgAndPrint(os.path.join(gdb,tb))
    fixTableStrings(tb, gdb, whereclause)

datasets = arcpy.ListDatasets(wild_card=input_schema + '*', feature_type="feature")
datasets = [""] + datasets if datasets is not None else []
for ds in datasets:
    for fc in arcpy.ListFeatureClasses(wild_card=input_schema + '*', feature_dataset=ds):
        path = os.path.join(gdb, ds, fc)
        addMsgAndPrint(str(path))
        try:
            fixTableStrings(path, gdb, whereclause)
        except Exception as error:
            addMsgAndPrint(error)

addMsgAndPrint("DONE")



#-------------------validation script----------
import os
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
        self.params[1].enabled = False
        self.params[2].enabled = False           
        return

    def updateParameters(self):
        # Modify parameter values and properties.
        # This gets called each time a parameter is modified, before 
        # standard validation.
        gdb = self.params[0].valueAsText
        if getGDBType(gdb) == 'FileGDB':
            self.params[1].enabled = False
            self.params[2].enabled = False
        elif getGDBType(gdb) == 'EGDB':
            self.params[1].enabled = True    
            self.params[2].enabled = True 

            schemaList = []
            arcpy.env.workspace = gdb  
            datasets = arcpy.ListDatasets("*GeologicMap*", "Feature")	
            for dataset in datasets:
                schemaList.append(dataset.split('.')[0] + '.' + dataset.split('.')[1])
            self.params[1].filter.list = sorted(set(schemaList))	

            if self.params[1].value is not None:
                mapList = []
                for row in arcpy.da.SearchCursor(gdb + '\\' + self.params[1].value + '.Domain_MapName',['code']):
                    mapList.append(row[0])
                self.params[2].filter.list = sorted(set(mapList))         
        return

    def updateMessages(self):
        # Customize messages for the parameters.
        # This gets called after standard validation.
        return

    # def isLicensed(self):
    #     # set tool isLicensed.
    # return True
