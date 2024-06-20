import colortrans, sys, arcpy, os
from GeMS_utilityFunctions import *

gdb = arcpy.GetParameterAsText(0)
input_schema = arcpy.GetParameterAsText(1)
input_mapname = arcpy.GetParameterAsText(2)

fields = ('Symbol','AreaFillRGB')

if getGDBType(gdb) == 'FileGDB':
    dmu = gdb + '/DescriptionOfMapUnits'
    whereclause = "OBJECTID > 0"
elif getGDBType(gdb) == 'EGDB' and input_mapname == '':
    dmu = os.path.join(gdb + '/' + input_schema + '.DescriptionOfMapUnits')
    whereclause = "OBJECTID > 0"
elif getGDBType(gdb) == 'EGDB' and input_mapname != '':
    dmu = os.path.join(gdb + '/' + input_schema + '.DescriptionOfMapUnits')
    whereclause = "MapName = '" + input_mapname + "'"
    
edit = arcpy.da.Editor(gdb)
edit.startEditing(False, True)
edit.startOperation()     
with arcpy.da.UpdateCursor(dmu, fields, where_clause = whereclause) as cursor:
    for row in cursor:
        if row[0] != None:
            try:
                rgb = colortrans.wpg2rgb(row[0])
                r,g,b = rgb.split(',')
                rr = r.zfill(3)
                gg = g.zfill(3)
                bb = b.zfill(3)
                rrggbb = rr+','+gg+','+bb
                addMsgAndPrint(str(row)+', '+rgb+', '+rrggbb)
                cursor.updateRow([row[0],rrggbb])
            except:
                addMsgAndPrint('Symbol = '+str(row[0])+': failed to assign RGB value')
        else:
            addMsgAndPrint('No Symbol value')
edit.stopOperation()
edit.stopEditing(True)


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
        if getGDBType(gdb) == 'EGDB':
            self.params[1].enabled = True    
            schemaList = []
            arcpy.env.workspace = gdb  
            datasets = arcpy.ListDatasets("*GeologicMap*", "Feature")	
            for dataset in datasets:
                schemaList.append(dataset.split('.')[0] + '.' + dataset.split('.')[1])
            self.params[1].filter.list = sorted(set(schemaList))	

            if self.params[1].value is not None and len(arcpy.ListTables(self.params[1].value + '.Domain_MapName')) == 1:
                self.params[2].enabled = True
                mapList = []
                for row in arcpy.da.SearchCursor(gdb + '\\' + self.params[1].value + '.Domain_MapName',['code']):
                    mapList.append(row[0])
                self.params[2].filter.list = sorted(set(mapList)) 
            else:
                self.params[2].enabled = False
                self.params[2].value = None 
        else:
            self.params[1].enabled = False
            self.params[1].value = None 
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
