# ---------------------------------------------------------------------------
# Updates the MapName domain
# Run by administrator logged in as the schema user/owner
# Used as source script tool:  GeMS_Toolbox...Create and Edit...MapName Domain Update
#
# April 2024 - Christian Halsted, Maine Geological Survey
# ---------------------------------------------------------------------------

# Import system modules
from __future__ import print_function, unicode_literals, absolute_import
import sys, string, os, re, arcpy

debug = False

def showPyMessage(message):
    arcpy.AddMessage(message)
    print(message)

if __name__ == '__main__':
    db = arcpy.GetParameterAsText(0) #sys.argv[1] 
    arcpy.env.workspace = db
    datasets = arcpy.ListDatasets("*GeologicMap*", "Feature")[0]
    dbname = dataset.split('.')[0]
    dbNameUserPrefix = dbname + '.' + arcpy.GetParameterAsText(1) + '.'
    
    # add the Domain_MapName view to the EGDB for use by the MapName Domain Update tool
    if not arcpy.Exists(thisDB + "/" + dbNameUserPrefix + 'Domain_MapName'):
        arcpy.management.CreateDatabaseView(thisDB, "Domain_MapName", "SELECT TOP 5000 code, [description] FROM (SELECT MapName AS code, MapName AS [description] FROM " + dbNameUserPrefix + "MAPUNITPOLYS_evw GROUP BY MapName UNION SELECT MapName AS code, MapName AS [description] FROM " + dbNameUserPrefix + "CONTACTSANDFAULTS_evw GROUP BY MapName UNION SELECT MapName AS code, MapName AS [description] FROM " + dbNameUserPrefix + "STATIONS_evw GROUP BY MapName UNION SELECT MapName AS code, MapName AS [description] FROM " + dbNameUserPrefix + "GEOLOGICPOINTS_evw GROUP BY MapName) t ORDER BY code")
            
    showPyMessage(db + "/" + dbNameUserPrefix + "Domain_MapName domain values")
    arcpy.management.TableToDomain(db + "/" + dbNameUserPrefix + "Domain_MapName", "code", "description", db, dbNameUserPrefix + "MapNameValues", "description", "REPLACE")
 
#-------------------validation script----------
import arcpy
class ToolValidator:
  # Class to add custom behavior and properties to the tool and tool parameters.

    def __init__(self):
        # set self.params for use in other function
        self.params = arcpy.GetParameterInfo()

    def initializeParameters(self):
        # Customize parameter properties. 
        # This gets called when the tool is opened.
        return

    def updateParameters(self):
        schemaList = []
        arcpy.env.workspace = str(self.params[0].value)
        datasets = arcpy.ListDatasets("*GeologicMap*", "Feature")	
        for dataset in datasets:
            dbname = dataset.split('.')[0]
            schemaList.append(dataset.split('.')[1])
        self.params[1].filter.list = sorted(set(schemaList))	    
        return

    def updateMessages(self):
        # Customize messages for the parameters.
        # This gets called after standard validation.
        return

    def isLicensed(self):
        # set tool isLicensed.
        return True