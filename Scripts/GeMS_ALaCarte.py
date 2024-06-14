"""Add GeMS objects a la carte to a geodatabase

    Create or augment a GeMS or GeMS-like file geodatabase by adding one or more
    objects as needed

    Attributes:
        gdb (string): path to an existing file geodatbase. Use the new file
        geodatabase context menu option when browsing to a folder to create 
        a new empty geodatabase

        gdb_items (list): a list of new GeMS ojbects to add to the gdb. Each object
        can have three items:
        [[new or existing feature dataset, spatial reference of fd, table]]
    
    Returns:
        A feature dataset or a featureclass/non-spatial table either within 
        a feature dataset, if included, or within the file geodatabase if no
        feature dataset is included. 
        
        Feature dataset or table names picked from the dropdown may include 
        prefixes to customize the object. If the name of a table is being changed,
        the fields will still be based on the template name in the dropdown list.
        
        When customizing GenericPoints or GenericSamples, add a prefix but do
        not delete the word 'Generic'. This is necessary for the tool to find the
        correct template name. In the resulting feature class, 'Generic' will be
        omitted.

        DataSources and Glossary tables will be added even if not picked on the
        parameter form.
"""

import arcpy
import GeMS_Definition as gdef
import GeMS_utilityFunctions as guf
from pathlib import Path
import sys

versionString = "GeMS_ALaCarte.py, version of 5/8/24"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_ALaCarte.py"
guf.checkVersion(versionString, rawurl, "gems-tools-pro")

dbNameUserPrefix = ''

debug = False
geom_dict = {
    "CMULines": "Polyline",
    "CMUMapUnitPolys": "Polygon",
    "CMUPoints": "Point",
    "CartographicLines": "Polyline",
    "CartographicPoints": "Point",
    "ContactsAndFaults": "Polyline",
    "DataSourcePolys": "Polygon",
    "DataSources": "table",
    "DescriptionOfMapUnits": "table",
    "FossilPoints": "Point",
    "GenericPoints": "Point",
    "GenericSamples": "point",
    "GeoMaterialDict": "table",
    "GeochronPoints": "point",
    "GeologicLines": "Polyline",
    "GeologicPoints": "Point",
    "Glossary": "table",
    "IsoValueLines": "Polyline",
    "LayerList": "table",
    "MapUnitLines": "Polyline",
    "MapUnitOverlayPolys": "Polygon",
    "MapUnitPoints": "Point",
    "MapUnitPolys": "Polygon",
    "MiscellaneousMapInformation": "table",
    "OrientationPoints": "Point",
    "OverlayPolys": "Polygon",
    "PhotoPoints": "Point",
    "RepurposedSymbols": "table",
    "StandardLithology": "table",
    "Stations": "Point",
}

transDict = {
    "String": "TEXT",
    "Single": "FLOAT",
    "Double": "DOUBLE",
    "NoNulls": "NULLABLE",  # NB-enforcing NoNulls at gdb level creates headaches; instead, check while validating
    "NullsOK": "NULLABLE",
    "Optional": "NULLABLE",
    "Date": "DATE",
}


def eval_prj(prj_str, fd):
    unk_fds = [
        "CrossSection",
        "CorrelationOfMapUnits",
    ]
    if any([x in fd for x in unk_fds]):
        # create 'UNKNOWN' spatial reference
        sr = ""
    else:
        sr = arcpy.SpatialReference()
        sr.loadFromString(prj_str)
        if sr.name == "":
            sr = ""

    return sr


def find_temp(fc):
    names = geom_dict.keys()
    n = []
    for name in names:
        if name in fc:
            n = [name, geom_dict[name]]
            break
    if n:
        return n[0], n[1]
    else:
        return None, None


def conf_domain(gdb):
    l_domains = [d.name for d in arcpy.da.ListDomains(gdb)]
    if debug:
        arcpy.AddMessage("l_domains=" + str(l_domains))                                  
    if not dbNameUserPrefix + "ExIDConfidenceValues" in l_domains:
        conf_vals = gdef.DefaultExIDConfidenceValues
        arcpy.AddMessage("Adding domain ExIDConfidenceValues")
        arcpy.CreateDomain_management(
            gdb, dbNameUserPrefix + "ExIDConfidenceValues", "", "TEXT", "CODED", "DUPLICATE"
        )
        for val in conf_vals:
            arcpy.AddMessage(f" Adding value {val[0]}")
            arcpy.AddCodedValueToDomain_management(
                gdb, dbNameUserPrefix + "ExIDConfidenceValues", val[0], val[0]
            )


def style_domain(gdb):
    l_domains = [d.name for d in arcpy.da.ListDomains(gdb)]
    if not "ParagraphStyleValues" in l_domains:
        arcpy.AddMessage("Adding domain ParagraphStyleValues")
        arcpy.CreateDomain_management(
            gdb, "ParagraphStyleValues", "", "TEXT", "CODED", "DUPLICATE"
        )
        for val in gdef.ParagraphStyleValues:
            arcpy.AddMessage(f"  Adding value {val}")
            arcpy.AddCodedValueToDomain_management(
                gdb, "ParagraphStyleValues", val, val
            )


def required(value_table):
    found = False
    # collect the values from the valuetable
    for t in ["DataSources", "Glossary"]:
        for i in range(0, value_table.rowCount):
            vals = value_table.getRow(i).split(" ")
            if t in vals:
                found = True
        if not found:
            value_table.addRow(["", "", f"{t}"])

    return value_table


def add_geomaterial(db, out_path, padding):
    # check for the GeoMaterialDict table and related domains and add them
    # if they are not found in gdb. The table and domain will be added if
    # 1. GeoMaterialDict is requested or
    # 2. if a version of MapUnitPolys (with GeoMaterial field) is requested
    arcpy.env.workspace = db
    if not "GeoMaterialDict" in arcpy.ListTables(db):
        arcpy.AddMessage("Creating GeoMaterialDict")
        geomat_csv = str(Path(__file__).parent / "GeoMaterialDict.csv")
        arcpy.TableToTable_conversion(geomat_csv, out_path, "GeoMaterialDict")

    # look for domains
    # GeoMaterials
    if is_gdb:
        l_domains = [d.name for d in arcpy.da.ListDomains(db)]
        if not "GeoMaterials" in l_domains:
            arcpy.AddMessage(f"{padding}Adding domain GeoMaterials")
            arcpy.TableToDomain_management(
                geomat_csv,
                "GeoMaterial",
                "GeoMaterial",
                db,
                "GeoMaterials",
            )

        # GeoMaterialConfidenceValues
        if not "GeoMaterialConfidenceValues" in l_domains:
            conf_vals = gdef.GeoMaterialConfidenceValues
            arcpy.AddMessage(f"{padding}Adding domain GeoMaterialConfidenceValues")
            arcpy.CreateDomain_management(
                db, dbNameUserPrefix + "GeoMaterialConfidenceValues", "", "TEXT", "CODED", "DUPLICATE"
            )
            for val in conf_vals:
                arcpy.AddMessage(f"{padding}  Adding value {val}")
                arcpy.AddCodedValueToDomain_management(
                    db, dbNameUserPrefix + "GeoMaterialConfidenceValues", val, val
                )


def process(db, value_table):
    global is_gdb
    is_gdb = False
    if db.endswith(".gdb") or db.endswith(".sde"):
        is_gdb = True

    # check for DataSources and Glossary
    value_table = required(value_table)
    if debug:
        arcpy.AddMessage("value_table=" + str(value_table))                
    # if gdb/geopackage doesn't exist, make it
    if not Path(db).exists:
        folder = Path(db).parent
        name = Path(db).stem
        if is_gdb:
            arcpy.CreateFileGDB_management(folder, name)
        else:
            arcpy.CreateSQLiteDatabase_management(db, "GEOPACKAGE_1.3")

    # collect the values from the valuetable
    for i in range(0, value_table.rowCount):
        out_path = db
        fd = value_table.getValue(i, 0)
        sr_prj = value_table.getValue(i, 1)
        sr = eval_prj(sr_prj, fd)
        fc = value_table.getValue(i, 2)

        if is_gdb:
            conf_domain(db)
            style_domain(db)

        # feature dataset
        fd_tab = ""
        if is_gdb:
            if not fd == "":
                fd_path = Path(db) / fd
                if arcpy.Exists(str(fd_path)):
                    arcpy.AddMessage(f"Found existing {fd} feature dataset")
                    sr = arcpy.da.Describe(str(fd_path))["spatialReference"]
                else:
                    arcpy.CreateFeatureDataset_management(db, fd, sr)
                    arcpy.AddMessage(f"New feature dataset {fd} created")
                out_path = str(fd_path)
                fd_tab = "  "

        # feature class or table
        template = None
        if not fc == "":
            fc_name = fc.replace("Generic", "")
            fc_path = Path(out_path) / fc_name
            if arcpy.Exists(str(fc_path)):
                arcpy.AddWarning(f"{fd_tab}{fc_name} already exists")
                template, shape = find_temp(fc)
            else:
                arcpy.AddMessage(f"{fd_tab}Creating {fc_name}")
                if fc == "GeoMaterialDict":
                    add_geomaterial(db, out_path, f"{fd_tab}  ")
                else:
                    template, shape = find_temp(fc)
                    if template:
                        if shape == "table":
                            arcpy.CreateTable_management(out_path, fc_name)
                        else:
                            arcpy.CreateFeatureclass_management(
                                out_path,
                                fc_name,
                                shape,
                                spatial_reference=sr,
                            )
                    else:
                        arcpy.AddWarning(
                            f"GeMS template for {fc_name} could not be found"
                        )
            fc_tab = "  "

            # add fields as defined in GeMS_Definition
            if template:
                fc_fields = [f.name for f in arcpy.ListFields(fc_path)]
                field_defs = gdef.startDict[template]
                
                #adds multimap fields to field_defs if creating an EGDB or removes them if they are in field_defs and creating a file geodatabase
                if db[-4:] == ".sde":
                    for field in gdef.multimap_fields:
                        if field not in field_defs:
                            field_defs.append(field)
                elif db[-4:] == ".gdb":
                    for field in gdef.multimap_fields:
                        if field in field_defs:
                            field_defs.remove(field)                
                #guf.showPyMessage(field_defs)
                for fDef in field_defs:
                    if not fDef[0] in fc_fields:
                        try:
                            arcpy.AddMessage(f"{fd_tab}{fc_tab}Adding field {fDef[0]}")
                            if fDef[1] == "String":
                                arcpy.AddField_management(
                                    str(fc_path),
                                    fDef[0],
                                    transDict[fDef[1]],
                                    field_length=fDef[3],
                                    field_is_nullable="NULLABLE",
                                )
                            else:
                                arcpy.AddField_management(
                                    str(fc_path),
                                    fDef[0],
                                    transDict[fDef[1]],
                                    field_is_nullable="NULLABLE",
                                )
                            fld_tab = " "
                        except:
                            arcpy.AddWarning(
                                f"Failed to add field {fDef[0]} to feature class {fc}"
                            )
                    else:
                        fld_tab = ""

                    if is_gdb:
                        # add domain for Ex, Id, Sci confidence fields
                        if fDef[0] in (
                            "ExistenceConfidence",
                            "IdentityConfidence",
                            "ScientificConfidence",
                        ):
                            try:
                                this_field = arcpy.ListFields(fc_path, fDef[0])[0]
                                if not this_field.domain == dbNameUserPrefix + "ExIDConfidenceValues":
                                    arcpy.AssignDomainToField_management(
                                        str(fc_path), fDef[0], dbNameUserPrefix + "ExIDConfidenceValues"
                                    )
                                    arcpy.AddMessage(
                                        f"{fd_tab}{fc_tab}{fld_tab}Domain ExIDConfidenceValues assigned to field {fDef[0]}"
                                    )
                            except:
                                arcpy.AddWarning(
                                    f"Failed to assign domain ExIDConfidenceValues to field {fDef[0]}"
                                )

                        
                        #add domain for multimap_fields
                        for flds in gdef.multimap_fields:
                            if fDef[0] == flds[0]:
                                try:
                                    this_field = arcpy.ListFields(fc_path, fDef[0])[0]
                                    if not this_field.domain == dbNameUserPrefix + flds[0] + "Values":
                                        arcpy.AssignDomainToField_management(str(fc_path), fDef[0], dbNameUserPrefix + flds[0] + "Values")
                                        arcpy.AddMessage(f"{fd_tab}{fc_tab}{fld_tab}Domain {dbNameUserPrefix + flds[0]}Values assigned to field {fDef[0]}")
                                except:
                                    arcpy.AddWarning(f"Failed to assign domain {dbNameUserPrefix + flds[0]}Values to field {fDef[0]}")                                
                        if fDef[0] == "GeoMaterial":
                            # try:
                            this_field = arcpy.ListFields(fc_path, "GeoMaterial")[0]
                            if not this_field.domain == dbNameUserPrefix + "GeoMaterials":
                                # double-check GeoMaterialDict and related domains
                                add_geomaterial(
                                    db, out_path, f"{fd_tab}{fc_tab}{fld_tab}"
                                )
                                arcpy.AssignDomainToField_management(
                                    str(fc_path), fDef[0], dbNameUserPrefix + "GeoMaterials"
                                )
                                arcpy.AddMessage(
                                    f"{fd_tab}{fc_tab}{fld_tab}GeoMaterials domain assigned to field GeoMaterial"
                                )

                        if fDef[0] == "ParagraphStyle":
                            try:
                                this_field = arcpy.ListFields(fc_path, fDef[0])[0]
                                if not this_field.domain == "ParagraphStyleValues":
                                    arcpy.AssignDomainToField_management(
                                        str(fc_path), fDef[0], "ParagraphStyleValues"
                                    )
                                    arcpy.AddMessage(
                                        f"{fd_tab}{fc_tab}{fld_tab}Domain ParagraphStyleValues assigned to field {fDef[0]}"
                                    )
                            except:
                                arcpy.AddWarning(
                                    f"Failed to assign domain ParagraphStyleValues to field {fDef[0]}"
                                )
                            # except:
                            #     arcpy.AddWarning(
                            #         f"Failed to assign domain GeoMaterials to field GeoMaterial"
                            #     )

                        # add domain for GeoMaterialConfidence
                        if fDef[0] == "GeoMaterialConfidence":
                            try:
                                this_field = arcpy.ListFields(
                                    fc_path, "GeoMaterialConfidence"
                                )[0]
                                if (
                                    not this_field.domain
                                    == dbNameUserPrefix + "GeoMaterialConfidenceValues"
                                ):
                                    # double-check GeoMaterialDict and related domains
                                    add_geomaterial(
                                        db, out_path, f"{fd_tab}{fc_tab}{fld_tab}"
                                    )
                                    arcpy.AssignDomainToField_management(
                                        str(fc_path),
                                        fDef[0],
                                        dbNameUserPrefix + "GeoMaterialConfidenceValues",
                                    )
                                    arcpy.AddMessage(
                                        f"{fd_tab}{fc_tab}{fld_tab}GeoMaterialConfidenceValues domain assigned to field GeoMaterialConfidenceValue"
                                    )
                            except:
                                arcpy.AddWarning(
                                    f"Failed to assign domain GeoMaterialConfidenceValues to field GeoMaterialConfidenceValue"
                                )

                try:
                    if not f"{fc_name}_ID" in fc_fields:
                        # add a _ID field
                        arcpy.AddMessage(f"{fd_tab}{fc_tab}Adding field {fc_name}_ID")
                        arcpy.AddField_management(
                            str(fc_path), f"{fc_name}_ID", "TEXT", field_length=50
                        )
                except:
                    arcpy.AddWarning(f"Could not add field {fc_name}_ID")


if __name__ == "__main__":
    db = sys.argv[1]
    # gdb_items = sys.argv[2]
    value_table = arcpy.GetParameter(1)
    if guf.getGDBType(db) == 'EGDB':
        desc = arcpy.Describe(db)
        cp = desc.connectionProperties
        dbUser = cp.user
        dbName = cp.database
        dbNameUserPrefix = dbName + '.' + dbUser + '.'                                      
    process(db, value_table)





#-------------------validation script----------
import sys
from pathlib import Path
parent = Path(__file__).parent
scripts = parent / 'scripts'
sys.path.append(str(scripts))
import GeMS_Definition as gdef
import GeMS_utilityFunctions as guf

def build_dict(gdb):
    import os
    gdb_dict = {}   
    arcpy.env.workspace = gdb
    datasets = arcpy.ListDatasets(feature_type='feature')
    datasets = [''] + datasets if datasets is not None else []

    for ds in datasets:
        for fc in arcpy.ListFeatureClasses(feature_dataset=ds):
            path = os.path.join(arcpy.env.workspace, ds, fc)
            gdb_dict[fc] = path
    for tbl in arcpy.ListTables():
        path = os.path.join(arcpy.env.workspace, tbl)
        gdb_dict[tbl] = path
    return gdb_dict

class ToolValidator:
  # Class to add custom behavior and properties to the tool and tool parameters.
    
    def __init__(self):
        # set self.params for use in other function
        self.params = arcpy.GetParameterInfo()
        tables = list(gdef.startDict.keys())
        tables.sort()
        self.params[1].filters[2].list = tables

    def initializeParameters(self):
        # Customize parameter properties. 
        # This gets called when the tool is opened.
        self.params[2].enabled = False
        return

    def updateParameters(self):
        # Modify parameter values and properties.
        # This gets called each time a parameter is modified, before 
        # standard validation.  
        gems_fds = {'CorrelationOfMapUnits', 'CrossSection', 'GeologicMap'}
        if not self.params[0].hasBeenValidated:  
            if self.params[0].value:      
                gdb = self.params[0].valueAsText
                if arcpy.Exists(gdb):
                    if gdb.endswith(".gdb") or gdb.endswith(".sde") or gdb.endswith(".gpkg"):
                        # store a dictionary of fc:fc_path from the gdb in the 
                        # parameter 2 text box (enabled = False in initializeParameters
                        gdb_path = Path(gdb)
                        gdb_dict = build_dict(str(gdb_path))   
                        self.params[2].value = str(gdb_dict)
                    if gdb.endswith(".gdb") or gdb.endswith(".sde"):
                        arcpy.env.workspace = self.params[0].value
                        fds = set(arcpy.ListDatasets(feature_type='Feature'))
                        col_fds = list(fds.union(gems_fds))
                        col_fds.sort()
                        self.params[1].filters[0].list = col_fds
            else:
                self.params[2].value = None
    
        if self.params[1].value and not self.params[1].hasBeenValidated:
            tab_vals = self.params[1].values
                    
            for row in tab_vals:
                fd = row[0]
                arcpy.env.workspace = self.params[0].value
                if fd in arcpy.ListDatasets(feature_type='Feature'):
                    sr = arcpy.da.Describe(fd)['spatialReference']
                    if sr.name == "Unknown":
                        row[1] = None
                    else:
                        row[1] = sr.name
                else:
                    row[1] = row[1].name
            self.params[1].values = tab_vals

        return

    def updateMessages(self):
        # Customize messages for the parameters.
        # This gets called after standard validation.
    
        if '00800' in self.params[1].message:
            self.params[1].clearMessage()

        if self.params[2].value and self.params[1].values:
            if self.params[0].valueAsText.endswith(".gdb"):
                gdb = Path(self.params[0].valueAsText)
                val_dict = {}
                
                # retrieve the fc_dict dictionary from parameter 2 text box
                gdb_dict = eval(self.params[2].valueAsText)
                
                # make a similar dictionary from the value table in parameter 1
                val_tab = self.params[1].values 
                for row in val_tab:
                    fd = row[0]
                    fc = row[2]
                    if fc:
                        val_dict[fc] = str(gdb / fd / fc)
                        
                if val_dict:
                    for k in val_dict:
                        if k in gdb_dict:
                            if gdb_dict[k] != val_dict[k]:
                                ws = Path(gdb_dict[k]).parent.stem
                                self.params[1].setErrorMessage(
                                  f"{k} already exists in workspace {ws} \n Add a prefix to customize the name"
                                  )

        return

    # def isLicensed(self):
    #     # set tool isLicensed.
    # return True

    # def postExecute(self):
    #     # This method takes place after outputs are processed and
    #     # added to the display.
    # return