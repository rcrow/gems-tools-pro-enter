#  GeMS_TranslateToShape_AGP2.py
#
#  Converts an GeMS-style ArcGIS geodatabase to
#    open file format
#      shape files, .csv files, and pipe-delimited .txt files,
#      without loss of information.  Field renaming is documented in
#      output file logfile.txt
#    simple shapefile format
#      basic map information in flat shapefiles, with much repetition
#      of attribute information, long fields truncated, and much
#      information lost. Field renaming is documented in output file
#      logfile.txt
#
#  Ralph Haugerud, USGS, Seattle
#    rhaugerud@usgs.gov

# 10 Dec 2017. Fixed bug that prevented dumping of not-GeologicMap feature datasets to OPEN version
# 27 June 2019. Many fixes when investigating Issue 30 (described at master github repo)
# 18 July 2019. Just a few syntax edits to make it usable in ArcGIS Pro with Python 3
#  renamed to GeMS_TranslateToShape_AGP2.py

import arcpy
import sys, os, glob, time
import datetime
import glob
from GeMS_utilityFunctions import *
from numbers import Number

versionString = "GeMS_TranslateToShape.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_TranslateToShape.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

debug = True

input_schema = ''
input_mapname = ''
    
# equivalentFraction is used to rank ProportionTerms from most
#  abundant to least
equivalentFraction = {
    "all": 1.0,
    "only part": 1.0,
    "dominant": 0.6,
    "major": 0.5,
    "significant": 0.4,
    "subordinate": 0.3,
    "minor": 0.25,
    "trace": 0.05,
    "rare": 0.02,
    "variable": 0.01,
    "present": 0.0,
}


def usage():
    addMsgAndPrint(
        """
USAGE: GeMS_TranslateToShape.py  <geodatabase> <outputWorkspace>
  where <geodatabase> must be an existing ArcGIS file geodatabase, and the 
  .gdb extension must be included.
  Output is written to directories <geodatabase (no extension)>-simple
  and <geodatabase (no extension)>-open in <outputWorkspace>. Output 
  directories, if they already exist, will be overwritten.
"""
    )


shortFieldNameDict = {
    "IdentityConfidence": "IdeConf",
    "MapUnitPolys_ID": "MUPs_ID",
    "Description": "Descr",
    "HierarchyKey": "HKey",
    "ParagraphStyle": "ParaSty",
    "AreaFillRGB": "RGB",
    "AreaFillPatternDescription": "PatDes",
    "GeoMaterial": "GeoMat",
    "GeoMaterialConfidence": "GeoMatConf",
    "IsConcealed": "IsCon",
    "LocationConfidenceMeters": "LocConfM",
    "ExistenceConfidence": "ExiConf",
    "ContactsAndFaults_ID": "CAFs_ID",
    "PlotAtScale": "PlotAtSca",
}

forget = ["objectid", "shape", "ruleid", "ruleid_1", "override"]

joinTablePrefixDict = {
    "DescriptionOfMapUnits_": "DMU",
    "DataSources_": "DS",
    "Glossary_": "GL",
}


def lookup_prefix(f_name):
    for table in joinTablePrefixDict.keys():
        if f_name.find(table) == 0:
            return joinTablePrefixDict[table]
    else:
        return ""


def remapFieldName(name):
    if name in shortFieldNameDict:
        return shortFieldNameDict[name]
    elif len(name) <= 10:
        return name
    else:
        name2 = name.replace("And", "")
        name2 = name2.replace("Of", "")
        name2 = name2.replace("Unit", "Un")
        name2 = name2.replace("Source", "Src")
        name2 = name2.replace("Shape", "Shp")
        name2 = name2.replace("shape", "Shp")
        name2 = name2.replace("SHAPE", "Shp")
        name2 = name2.replace("Hierarchy", "H")
        name2 = name2.replace("Description", "Descript")
        name2 = name2.replace("AreaFill", "")
        name2 = name2.replace("Structure", "Struct")
        name2 = name2.replace("STRUCTURE", "STRUCT")
        name2 = name2.replace("user", "Usr")
        name2 = name2.replace("created_", "Cre")
        name2 = name2.replace("edited_", "Ed")
        name2 = name2.replace("date", "Dt")
        name2 = name2.replace("last_", "Lst")

        newName = ""
        for i in range(0, len(name2)):
            if name2[i] == name2[i].upper():
                newName = newName + name2[i]
                j = 1
            else:
                j = j + 1
                if j < 4:
                    newName = newName + name2[i]
        if len(newName) > 10:
            if newName[1:3] == newName[1:3].lower():
                newName = newName[0] + newName[3:]
        if len(newName) > 10:
            if newName[3:5] == newName[3:5].lower():
                newName = newName[0:2] + newName[5:]
        if len(newName) > 10:
            # as last resort, just truncate to 10 characters
            # might be a duplicate, but exporting to shapefile will add numbers to the
            # duplicates. Those names just won't match what will be recorded in the logfile
            newName = newName[:10]
        return newName


def check_unique(fieldmappings):
    out_names = [fm.outputField.name for fm in fieldmappings]
    dup_names = set([x for x in out_names if out_names.count(x) > 1])
    for dup_name in dup_names:
        i = 0
        for fm in fieldmappings:
            if fm.outputField.name == dup_name:
                prefix = lookup_prefix(fm.getInputFieldName(0))
                new_name = remapFieldName(prefix + dup_name)
                out_field = fm.outputField
                out_field.name = new_name
                fm.outputField = out_field
                fieldmappings.replaceFieldMap(i, fm)
            i = i + 1


def dumpTable(fc, outName, isSpatial, outputDir, logfile, isOpen, fcName):
    dumpString = "  Dumping {}...".format(outName)
    if isSpatial:
        dumpString = "  " + dumpString
    addMsgAndPrint(dumpString)
    if isSpatial:
        logfile.write("  feature class {} dumped to shapefile {}\n".format(fc, outName))
    else:
        logfile.write("  table {} dumped to table\n".format(fc, outName))
    logfile.write("    field name remapping: \n")

    longFields = []
    fieldmappings = arcpy.FieldMappings()
    fields = arcpy.ListFields(fc)
    for field in fields:
        # get the name string and chop off the joined table name if necessary
        fName = field.name
        for prefix in ("DescriptionOfMapUnits", "DataSources", "Glossary", fcName):
            if fc != prefix and fName.find(prefix) == 0 and fName != fcName + "_ID":
                fName = fName[len(prefix) + 1 :]

        if not fName.lower() in forget:
            # make the FieldMap object based on this field
            fieldmap = arcpy.FieldMap()
            fieldmap.addInputField(fc, field.name)
            out_field = fieldmap.outputField

            # go back to the FieldMap object and set up the output field name
            out_field.name = remapFieldName(fName)
            fieldmap.outputField = out_field
            # logfile.write('      '+field.name+' > '+out_field.name+'\n')

            # save the FieldMap in the FieldMappings
            fieldmappings.addFieldMap(fieldmap)

        if field.length > 254:
            longFields.append(fName)

    check_unique(fieldmappings)
    for fm in fieldmappings:
        logfile.write(
            "      {} > {}\n".format(fm.getInputFieldName(0), fm.outputField.name)
        )

    if isSpatial:
        if debug:
            addMsgAndPrint("dumping {}, {}, {}".format(fc, outputDir, outName))
        try:
            arcpy.FeatureClassToFeatureClass_conversion(
                fc, outputDir, outName, field_mapping=fieldmappings
            )
        except:
            addMsgAndPrint("failed to translate table " + fc)
    else:
        arcpy.TableToTable_conversion(
            fc, outputDir, outName, field_mapping=fieldmappings
        )

    if isOpen:
        # if any field lengths > 254, write .txt file
        if len(longFields) > 0:
            outText = outName[0:-4] + ".txt"
            logfile.write(
                "    table "
                + fc
                + " has long fields, thus dumped to file "
                + outText
                + "\n"
            )
            csv_path = os.path.join(outputDir, outText)
            csvFile = open(csv_path, "w")
            fields = arcpy.ListFields(fc)
            f_names = [
                f.name for f in fields if f.type not in ["Blob", "Geometry", "Raster"]
            ]

            col_names = "|".join(f_names)
            csvFile.write("{}\n|".format(col_names))
            # addMsgAndPrint("FC name: "+ fc)
            with arcpy.da.SearchCursor(fc, f_names) as cursor:
                for row in cursor:
                    rowString = str(row[0])
                    for i in range(1, len(row)):  # use enumeration here?
                        # if debug: addMsgAndPrint("Index: "+str(i))
                        # if debug: addMsgAndPrint("Current row is: " + str(row[i]))
                        if row[i] != None:
                            xString = str(row[i])
                            if isinstance(row[i], Number) or isinstance(
                                row[i], datetime.datetime
                            ):
                                xString = str(row[i])
                            else:
                                # if debug: addMsgAndPrint("Current row type is: " + str(type(row[i])))
                                xString = row[i].encode("ascii", "xmlcharrefreplace")
                            # rowString = rowString+'|'+xString
                        else:
                            rowString = rowString + "|"
                    csvFile.write(rowString + "\n")
            csvFile.close()
    addMsgAndPrint("    Finished dump\n")


def makeOutputDir(newgdb, outws, isOpen):
    outputDir = os.path.join(outws, os.path.basename(newgdb)[2:-4])
    if isOpen:
        outputDir = outputDir + "-open"
    else:
        outputDir = outputDir + "-simple"
    addMsgAndPrint("Making {}...".format(outputDir))
    if os.path.exists(outputDir):
        arcpy.Delete_management(outputDir)
    os.mkdir(outputDir)
    logfile = open(os.path.join(outputDir, "logfile.txt"), "w")
    logfile.write("file written by " + versionString + "\n\n")
    return outputDir, logfile


def dummyVal(pTerm, pVal):
    if pVal == None:
        if pTerm in equivalentFraction:
            return equivalentFraction[pTerm]
        else:
            return 0.0
    else:
        return pVal


def description(unitDesc):
    unitDesc.sort()
    unitDesc.reverse()
    desc = ""
    for uD in unitDesc:
        if uD[3] == "":
            desc = desc + str(uD[4]) + ":"
        else:
            desc = desc + uD[3] + ":"
        desc = desc + uD[2] + "; "
    return desc[:-2]


def makeStdLithDict():
    addMsgAndPrint("  Making StdLith dictionary...")
    stdLithDict = {}
    rows = arcpy.SearchCursor("StandardLithology", "", "", "", "MapUnit")  
    row = rows.next()
    unit = row.getValue("MapUnit")
    unitDesc = []
    pTerm = row.getValue("ProportionTerm")
    pVal = row.getValue("ProportionValue")
    val = dummyVal(pTerm, pVal)
    unitDesc.append(
        [val, row.getValue("PartType"), row.getValue("Lithology"), pTerm, pVal]
    )
    while row:
        newUnit = row.getValue("MapUnit")
        if newUnit != unit:
            stdLithDict[unit] = description(unitDesc)
            unitDesc = []
            unit = newUnit
        pTerm = row.getValue("ProportionTerm")
        pVal = row.getValue("ProportionValue")
        val = dummyVal(pTerm, pVal)
        unitDesc.append(
            [val, row.getValue("PartType"), row.getValue("Lithology"), pTerm, pVal]
        )
        row = rows.next()
    del row, rows
    stdLithDict[unit] = description(unitDesc)
    if debug: addMsgAndPrint(str(stdLithDict))
    return stdLithDict


def mapUnitPolys(stdLithDict, outputDir, logfile):
    addMsgAndPrint("  Translating {}...".format(os.path.join("GeologicMap", "MapUnitPolys")))
    try:
        arcpy.MakeTableView_management("DescriptionOfMapUnits", "DMU")
                
        if stdLithDict != "None":
            arcpy.AddField_management("DMU", "StdLith", "TEXT", "", "", "255")
            rows = arcpy.UpdateCursor("DMU")
            row = rows.next()
            while row:
                if row.MapUnit in stdLithDict:
                    row.StdLith = stdLithDict[row.MapUnit]
                    rows.updateRow(row)
                row = rows.next()
            del row, rows

        arcpy.MakeFeatureLayer_management("GeologicMap/MapUnitPolys", "MUP")
        arcpy.AddJoin_management("MUP", "MapUnit", "DMU", "MapUnit")
        arcpy.AddJoin_management("MUP", "DataSourceID", "DataSources", "DataSources_ID")
        arcpy.CopyFeatures_management("MUP", "MUP2")
        DM = "descriptionofmapunits_"
        DS = "datasources_"
        MU = "mapunitpolys_"
        delete_fields = [
            MU + "datasourceid",
            MU + MU + "id",
            DM + "mapunit",
            DM + "objectid",
            DM + DM + "id",
            DM + "label",
            DM + "symbol",
            DM + "descriptionsourceid",
            DS + "objectid",
            DS + DS + "id",
            DS + "notes",
        ]
        for f in arcpy.ListFields("MUP2"):
            if f.name.lower() in delete_fields:
                arcpy.DeleteField_management("MUP2", f.name)

        dumpTable("MUP2", "MapUnitPolys.shp", True, outputDir, logfile, False, "MapUnitPolys")
    except:
        addMsgAndPrint(arcpy.GetMessages())
        addMsgAndPrint("  Failed to translate MapUnitPolys")
        print('')

    for lyr in ["DMU", "MUP", "MUP2"]:
        if arcpy.Exists(lyr):
            arcpy.Delete_management(lyr)


def linesAndPoints(fc, outputDir, logfile):
    addMsgAndPrint("  Translating {}...".format(fc))
    cp = fc.find("/")
    fcShp = fc[cp + 1 :] + ".shp"
    LIN2 = fc[cp + 1 :] + "2"
    LIN = "xx" + fc[cp + 1 :]

    # addMsgAndPrint('    Copying features from {} to {}'.format(fc, LIN2))
    arcpy.CopyFeatures_management(fc, LIN2)
    arcpy.MakeFeatureLayer_management(LIN2, LIN)
    fieldNames = fieldNameList(LIN)
    if "Type" in fieldNames:
        arcpy.AddField_management(LIN, "Definition", "TEXT", "#", "#", "254")
        arcpy.AddJoin_management(LIN, "Type", "Glossary", "Term")
        arcpy.CalculateField_management(LIN, "Definition", "!Glossary.Definition![0:254]", "PYTHON")
        arcpy.RemoveJoin_management(LIN, "Glossary")

    # command below are 9.3+ specific
    sourceFields = arcpy.ListFields(fc, "*SourceID")
    for sField in sourceFields:
        nFieldName = sField.name[:-2]
        arcpy.AddField_management(LIN, nFieldName, "TEXT", "#", "#", "254")
        arcpy.AddJoin_management(LIN, sField.name, "DataSources", "DataSources_ID")
        arcpy.CalculateField_management(LIN, nFieldName, "!DataSources.Source![0:254]", "PYTHON")
        arcpy.RemoveJoin_management(LIN, "DataSources")
        arcpy.DeleteField_management(LIN, sField.name)

    dumpTable(LIN2, fcShp, True, outputDir, logfile, False, fc[cp + 1 :])
    arcpy.Delete_management(LIN)
    arcpy.Delete_management(LIN2)


def main(newgdb, outws, gdb):
    ## Simple version
    isOpen = False
    if debug: addMsgAndPrint("newgdb: {}, outws: {}, gdb: {}".format(newgdb, outws, gdb))
    outputDir, logfile = makeOutputDir(newgdb, outws, isOpen) 
    arcpy.env.workspace = newgdb

    if "StandardLithology" in arcpy.ListTables():
        stdLithDict = makeStdLithDict()
    else:
        stdLithDict = "None"

    mapUnitPolys(stdLithDict, outputDir, logfile)

    arcpy.env.workspace = os.path.join(newgdb, "GeologicMap")
    pointfcs = arcpy.ListFeatureClasses("", "POINT")
    linefcs = arcpy.ListFeatureClasses("", "LINE")
    arcpy.env.workspace = newgdb
    for fc in linefcs:
        linesAndPoints(fc, outputDir, logfile)
    for fc in pointfcs:
        linesAndPoints(fc, outputDir, logfile)
    logfile.close()

    ## Open version
    isOpen = True
    outputDir, logfile = makeOutputDir(newgdb, outws, isOpen)

    # list featuredatasets
    arcpy.env.workspace = newgdb
    fds = arcpy.ListDatasets()

    # for each featuredataset
    for fd in fds:
        addMsgAndPrint("  Processing feature data set {}...".format(fd))
        logfile.write("Feature data set {}\n".format(fd))
        try:
            spatialRef = arcpy.Describe(fd).SpatialReference
            logfile.write("  spatial reference framework\n")
            logfile.write("    name = {}\n".format(spatialRef.Name))
            logfile.write("    spheroid = {}\n".format(spatialRef.SpheroidName))
            logfile.write("    projection = {}\n".format(spatialRef.ProjectionName))
            logfile.write("    units = {}\n".format(spatialRef.LinearUnitName))
        except:
            logfile.write("  spatial reference framework appears to be undefined\n")

        # generate featuredataset prefix
        pfx = ""
        for i in range(0, len(fd) - 1):
            if fd[i] == fd[i].upper():
                pfx = pfx + fd[i]

        arcpy.env.workspace = os.path.join(newgdb, fd)
        fcList = arcpy.ListFeatureClasses()
        if fcList != None:
            for fc in fcList:
                arcpy.AddMessage(fc)
                # don't dump Anno classes
                if arcpy.Describe(fc).featureType != "Annotation":
                    outName = "{}_{}.shp".format(pfx, fc)
                    dumpTable(fc, outName, True, outputDir, logfile, isOpen, fc)
                else:
                    addMsgAndPrint(
                        "    Skipping annotation feature class {}\n".format(fc)
                    )
        else:
            addMsgAndPrint("   No feature classes in this dataset!")
        logfile.write("\n")

    # list tables
    arcpy.env.workspace = newgdb
    for tbl in arcpy.ListTables():
        outName = tbl + ".csv"
        dumpTable(tbl, outName, False, outputDir, logfile, isOpen, tbl)
    logfile.close()


### START HERE ###
if (
    not os.path.exists(arcpy.GetParameterAsText(0))
    or not os.path.exists(arcpy.GetParameterAsText(1))
):
    usage()
else:
    addMsgAndPrint("  " + versionString)
    gdb = os.path.abspath(arcpy.GetParameterAsText(0))
    gdb_name = os.path.basename(gdb)
    outws = os.path.abspath(arcpy.GetParameterAsText(1))
    input_schema = arcpy.GetParameterAsText(2)
    input_mapname = arcpy.GetParameterAsText(3)
           
    arcpy.env.qualifiedFieldNames = False
    arcpy.env.overwriteOutput = True

    # fix the new workspace name so it is guaranteed to be novel, no overwrite
    if getGDBType(gdb) == 'FileGDB':
        newgdb = os.path.join(outws, "xx{}".format(gdb_name))
    elif getGDBType(gdb) == 'EGDB' and input_mapname == '':
        newgdb = os.path.join(outws, "xx{}.gdb".format('EGDB')) 
        whereclause="OBJECTID > 0"
    elif getGDBType(gdb) == 'EGDB' and input_mapname != '':
        newgdb = os.path.join(outws, "xx{}.gdb".format(input_mapname)) 
        whereclause="MapName = '" + input_mapname + "'"
    if debug: addMsgAndPrint(newgdb)
    
    addMsgAndPrint("  Copying {} to temporary geodatabase {}".format(os.path.basename(gdb), os.path.basename(newgdb)))
    if arcpy.Exists(newgdb):
        arcpy.Delete_management(newgdb)        
    if getGDBType(gdb) == 'FileGDB':
        arcpy.Copy_management(gdb, newgdb)
    elif getGDBType(gdb) == 'EGDB':
        #option 1 - run time 10 minutes
        #loop through all feature classes in each feature dataset
        arcpy.env.workspace = gdb
        arcpy.management.CreateFileGDB(os.path.dirname(newgdb), os.path.basename(newgdb))
        for fds in arcpy.ListDatasets(input_schema + '*'):
            addMsgAndPrint('creating feature dataset: ' + fds)
            sr = arcpy.Describe(fds).spatialReference
            arcpy.management.CreateFeatureDataset(newgdb, fds.replace(input_schema + '.',''), sr)
            for fc in arcpy.ListFeatureClasses(wild_card = input_schema + '*', feature_dataset = fds):
                addMsgAndPrint('copying feature class: ' + fc)
                arcpy.management.MakeFeatureLayer(fc, 'lyrCount', where_clause=whereclause)
                if int(arcpy.management.GetCount('lyrCount')[0]) > 0:
                    arcpy.conversion.FeatureClassToFeatureClass(fc, os.path.join(newgdb, fds.replace(input_schema + '.','')), fc.replace(input_schema + '.',''), where_clause=whereclause)
                arcpy.management.Delete('lyrCount')
        #loop through all feature classes not in feature datasets
        for fc in arcpy.ListFeatureClasses(wild_card = input_schema + '*'):
            addMsgAndPrint('copying feature class: ' + fc)
            arcpy.management.MakeFeatureLayer(fc, 'lyrCount', where_clause=whereclause)
            if int(arcpy.management.GetCount('lyrCount')[0]) > 0:
                arcpy.conversion.FeatureClassToFeatureClass(fc, newgdb, fc.replace(input_schema + '.',''), where_clause=whereclause)
            arcpy.management.Delete('lyrCount')
        #loop through all tables
        for table in arcpy.ListTables(wild_card = input_schema + '*'):
            addMsgAndPrint('copying table: ' + table)
            if len(arcpy.ListFields(table, 'MapName')) == 1:
                whereclause="MapName = '" + input_mapname + "'"
            elif table.replace(input_schema + '.','') == 'GeoMaterialDict':
                whereclause="OBJECTID > 0"
            else:
                whereclause= arcpy.ListFields(table)[0].name + ">'-1'"
            arcpy.management.MakeTableView(table, 'lyrCount', where_clause=whereclause)
            if int(arcpy.management.GetCount('lyrCount')[0]) > 0:
                arcpy.conversion.TableToTable(table, newgdb, table.replace(input_schema + '.',''), where_clause=whereclause)
            arcpy.management.Delete('lyrCount')
        #clean up empty feature datasets
        arcpy.env.workspace = newgdb
        for fds in arcpy.ListDatasets():
            if len(arcpy.ListFeatureClasses(wild_card = '', feature_dataset = fds))<1:
                arcpy.management.Delete(fds)
        
        # ##option 2 - run time 12 minutes, but copies data for all maps and alias for tables and fcs has db.schema 
        # # sdeConnection = gdb #'C:\\GeMS_Coop\\MGS_Data_LOCAL.sde'
        # # backupDestination = outws #'C:\\GeMS_Coop\\test-output'
        # # backupGdbName = "xx{}.gdb".format(input_mapname)  #'testscript.gdb'
        # # arcpy.CreateFileGDB_management(backupDestination, backupGdbName)
        # # backupGdbPath = os.path.join(backupDestination, backupGdbName)        
        # # for root, datasets, tables in arcpy.da.Walk(sdeConnection, followlinks=True):
            # # for dataset in datasets:
                # # sourceDatasetPath = os.path.join(root, dataset)
                # # backupDatasetPath = os.path.join(backupGdbPath, dataset.split(".")[-1])
                # # if input_schema in sourceDatasetPath:
                    # # addMsgAndPrint(f"{sourceDatasetPath}, {backupDatasetPath}")
                    # # arcpy.Copy_management(sourceDatasetPath, backupDatasetPath)
                    # # #sr = arcpy.Describe(sourceDatasetPath).spatialReference
                    # # #arcpy.management.CreateFeatureDataset(backupGdbPath, dataset.split(".")[-1], sr)
            # # for table in tables:
                # # # Ignore attachment tables, taken care of in the previous Copy_management
                # # if not table.endswith("__ATTACH") and input_schema in table:
                    # # sourceTableName = os.path.join(root, table)
                    # # itemDesc = arcpy.Describe(sourceTableName)
                    # # if itemDesc.dataType in ("Table", "FeatureClass"):
                        # # backupTableName = os.path.join(backupGdbPath, table.split(".")[-1])
                        # # if input_schema in sourceTableName:
                            # # addMsgAndPrint(sourceTableName)
                            # # arcpy.Copy_management(sourceTableName, backupTableName)        
            # # break

    main(newgdb, outws, gdb)

    # cleanup
    addMsgAndPrint("\n  Deleting temporary geodatabase")
    try:
        arcpy.Delete_management(newgdb)
    except:
        addMsgAndPrint("    As usual, failed to delete temporary geodatabase")
        addMsgAndPrint("    Please delete " + newgdb + "\n")




#-------------------validation script----------
import os
sys.path.insert(1, os.path.join(os.path.dirname(__file__),'Scripts'))
from GeMS_utilityFunctions import *
class ToolValidator:
    """Class for validating a tool's parameter values and controlling
    the behavior of the tool's dialog."""

    def __init__(self):
        """Setup the Geoprocessor and the list of tool parameters."""
        import arcgisscripting as ARC
        self.GP = ARC.create(9.3)
        self.params = self.GP.getparameterinfo()

    def initializeParameters(self):
        """Refine the properties of a tool's parameters.  This method is
        called when the tool is opened."""
        self.params[2].enabled = False
        self.params[3].enabled = False     
        return

    def updateParameters(self):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parmater
        has been changed."""
        gdb = self.params[0].valueAsText
        if getGDBType(gdb) == 'EGDB':
            self.params[2].enabled = True
            schemaList = []
            arcpy.env.workspace = gdb  
            datasets = arcpy.ListDatasets("*GeologicMap*", "Feature")	
            for dataset in datasets:
                schemaList.append(dataset.split('.')[0] + '.' + dataset.split('.')[1])
            self.params[2].filter.list = sorted(set(schemaList))	

            if self.params[2].value is not None and len(arcpy.ListTables(self.params[2].value + '.Domain_MapName')) == 1:
                self.params[3].enabled = True
                mapList = []
                for row in arcpy.da.SearchCursor(gdb + '\\' + self.params[2].value + '.Domain_MapName',['code']):
                    mapList.append(row[0])
                self.params[3].filter.list = sorted(set(mapList))  
            else:
                self.params[3].enabled = False
                self.params[3].value = None 
        else:
            self.params[2].enabled = False
            self.params[2].value = None 
            self.params[3].enabled = False
            self.params[3].value = None 
        return

    def updateMessages(self):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return