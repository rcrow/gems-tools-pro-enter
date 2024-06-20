"""Convert to geopackage

Creates a new geopackage based on a file geodatabase and then exports
all feature classe and tables to the new geopackage. Feature classes not in 
feature datasets and standalone tables not in a feature datasets retain 
the original name but feature classes inside feature datasets have the
name of the feature dataset pre-prended to the name of the feature class

Usage: 
    Provide the path to a .gdb, an optional output folder. If no output 
    directory is specified, the gpkg will be created in the parent folder
    of the input gdb. The resulting geopackage will have the same name 
    as the gdb with a .gpkg extension. Existing geopackages will be deleted 
    first and then recreated. The parameter form will warn the user about 
    an existing geopackage. They may proceed or pick a different output folder.

Args:
    input_gdb (str) : Path to database. Required.
    output_dir (str) : Path to folder in which to build the geopackage. Optional.
"""

import arcpy
from pathlib import Path
from GeMS_utilityFunctions import addMsgAndPrint as ap
import GeMS_utilityFunctions as guf

versionString = "GeMS_Convert2GPKG.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_Convert2GPKG.py"
guf.checkVersion(versionString, rawurl, "gems-tools-pro")

def makeMapNameWhereClause(obj, input_mapname):
    if len(arcpy.ListFields(obj,"MapName")) == 0:
        mapname_clause = ''
    elif len(arcpy.ListFields(obj,"MapName")) == 1:
        mapname_clause = "MapName='" + input_mapname + "'"
    return mapname_clause
    
def convert(input_gdb, input_schema, input_mapname, output_dir):
    # Set up input and output paths
    input_gdb = Path(input_gdb)
    if output_dir in (None, "", "#"):
        output_dir = input_gdb.parent

    output_gpkg = Path(output_dir) / f"{input_gdb.stem}.gpkg"

    if output_gpkg.exists():
        arcpy.Delete_management(str(output_gpkg))

    ap(f"Creating {input_gdb.stem}.gpkg")
    arcpy.CreateSQLiteDatabase_management(str(output_gpkg), "GEOPACKAGE_1.3")

    # Export feature classes in feature datasets
    arcpy.env.workspace = str(input_gdb)
    datasets = arcpy.ListDatasets(input_schema + '*')
    for dataset in datasets:
        fc_list = arcpy.ListFeatureClasses("", "", dataset)
        for fc in fc_list:
            fc_name = f"{dataset}_{fc}".replace(input_schema + '.','')
            ap(f"Exporting {fc} as {fc_name}")
            if arcpy.GetInstallInfo()['Version'][0] =='3':
                arcpy.ExportFeatures_conversion(f"{dataset}/{fc}", str(output_gpkg / fc_name), makeMapNameWhereClause(fc, input_mapname))
            if arcpy.GetInstallInfo()['Version'][0] =='2':   
                arcpy.conversion.FeatureClassToFeatureClass(str(input_gdb / dataset / fc), str(output_gpkg), fc_name, makeMapNameWhereClause(fc, input_mapname))
            
    # Export tables and feature classes outside feature datasets
    arcpy.env.workspace = str(input_gdb)
    fc_list = arcpy.ListFeatureClasses(input_schema + '*')            
    table_list = arcpy.ListTables(input_schema + '*')             
    for fc in fc_list:
        if input_schema in fc:
            ap(f"Exporting {fc}")                
            if arcpy.GetInstallInfo()['Version'][0] =='3':
                arcpy.ExportFeatures_conversion(fc, str(output_gpkg / fc), makeMapNameWhereClause(fc, input_mapname))
            if arcpy.GetInstallInfo()['Version'][0] =='2':   
                arcpy.conversion.FeatureClassToFeatureClass(str(input_gdb / fc), str(output_gpkg), fc.replace(input_schema + '.',''), makeMapNameWhereClause(fc, input_mapname))
    for table in table_list:
        if input_schema in table:
            ap(f"Exporting {table}")
            if arcpy.GetInstallInfo()['Version'][0] =='3':
                arcpy.ExportTable_conversion(table, str(output_gpkg / table), makeMapNameWhereClause(table, input_mapname))
            if arcpy.GetInstallInfo()['Version'][0] =='2':   
                arcpy.conversion.TableToTable(str(input_gdb / table), str(output_gpkg), table.replace(input_schema + '.',''), makeMapNameWhereClause(table, input_mapname))
                
    ap("Export complete.")


if __name__ == "__main__":
    param0 = arcpy.GetParameterAsText(0)
    param1 = arcpy.GetParameterAsText(1)
    param2 = arcpy.GetParameterAsText(2)
    param3 = arcpy.GetParameterAsText(3)

    convert(param0, param1, param2, param3)





#-------------------validation script----------
import os
from pathlib import Path
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
        gdb = self.params[0].valueAsText            
        gdb_name = Path(gdb).stem
        gpkg_name = f"{gdb_name}.gpkg"
        if not self.params[3].value is None:
            outdir = Path(self.params[3].valueAsText)           
        else:
            outdir = Path(Path(gdb).parent)
         
        gpkg = outdir / gpkg_name
        if Path.exists(gpkg):
            self.params[3].setWarningMessage(f"{str(gpkg)} already exists. This tool overwrites existing geopackages!")
        else:
            self.params[3].clearMessage()
        return

    # def isLicensed(self):
    #     # set tool isLicensed.
    # return True

    # def postExecute(self):
    #     # This method takes place after outputs are processed and
    #     # added to the display.
    # return