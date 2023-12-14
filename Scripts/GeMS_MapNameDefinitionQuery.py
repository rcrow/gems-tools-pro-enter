# ---------------------------------------------------------------------------
# Set the definition query to the MapName
# for all GeMS layers currently in the map 
# Used as source script tool:  GeMS_Toolbox...Create and Edit...MapName Definition Query
#
# Adapted from Maine Geological Survey SetDefinitionQuery tool
# July 2013 - Chris Halsted, Maine Geological Survey
# March 2021 - updated to work with ArcPro and Python 3
# September 2023 - migrated to work with GeMS Enterprise Geodatabase
# ---------------------------------------------------------------------------

# Import system modules
from __future__ import print_function, unicode_literals, absolute_import
import sys, string, os, re, arcpy

debug = False

def showPyMessage(message):
    arcpy.AddMessage(message)
    print(message)

def SetDefQuery(mapname,clear,draw):
    if clear == 'true': showPyMessage('Clearing map Definition Query')
    if clear == 'false': showPyMessage('Setting map Definition Query')
    mapfldname = 'MapName'
    drawfldname = 'DrawOnMap'
    
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    m = aprx.listMaps(aprx.activeMap.name)[0]
    for lyr in m.listLayers():
        if lyr.supports("dataSource"):
            if debug: showPyMessage(lyr.name)
            if debug: showPyMessage(lyr.longName)
            if debug: showPyMessage(lyr.dataSource)
            fcName=''
            for prop in lyr.dataSource.split(','):
                if prop[0:8] == 'Dataset=':
                    fcName = prop.replace('Dataset=','')
            if debug: showPyMessage(fcName)
            if fcName.find('_topology') == -1:
                if fcName.lower().find('gems') > -1 and mapfldname in [f.name for f in arcpy.ListFields(lyr.longName,'*','String')]: 
                    showPyMessage('Setting Defintion Query on ' + fcName)
                    #--clears any mapname from dq----------
                    if lyr.supports('DEFINITIONQUERY'):                           
                        dq = lyr.definitionQuery
                    else:
                        dq = ''
                    if debug: showPyMessage('dq0: ' + str(dq))
                    dq = dq.replace('AND','And')
                    if debug: showPyMessage('dq1: ' + str(dq))
                    
                    srchstr = dq[dq.find(mapfldname + " = '"):dq.find("'",dq.find(mapfldname + " = '")+(len(mapfldname + " = '")))+1]
                    if srchstr != "'" and len(srchstr)>0:
                        dq = dq.replace(" And " + srchstr, "")
                        dq = dq.replace(srchstr + " And ", "")
                        dq = dq.replace(srchstr, "")
                    if debug: showPyMessage('dq2: ' + str(dq))
                    
                    #sets new definition query
                    if clear == "true":
                        dq = dq.replace(" And " + mapfldname + " = '" + mapname + "'", "")
                        dq = dq.replace(mapfldname + " = '" + mapname + "'" + " And ", "")
                        dq = dq.replace(mapfldname + " = '" + mapname + "'", "")
                    elif clear == "false":
                        if len((dq).strip())==0:
                            dq = mapfldname + " = '" + mapname + "'"
                        else:
                            if mapfldname + " = '" + mapname + "'" not in dq:
                                dq = dq + " And " + mapfldname + " = '" + mapname + "'"
                    if debug: showPyMessage('dq3: ' + str(dq))
                    
                    if (mapfldname and drawfldname) in [f.name for f in arcpy.ListFields(lyr.longName,'*','String')]:
                        if draw == "true":
                            if drawfldname + " = 'Yes'" not in dq:
                                if len((dq).strip())==0:
                                    dq = dq + drawfldname + " = 'Yes'"
                                else:
                                    dq = dq + " And " + drawfldname + " = 'Yes'"
                        elif draw == "false":
                            dq = dq.replace(" And " + drawfldname + " = 'Yes'", "")
                            dq = dq.replace(drawfldname + " = 'Yes' And ", "")
                            dq = dq.replace(drawfldname + " = 'Yes'", "")
                    if debug: showPyMessage('dq4: ' + str(dq))
                    
                    if debug: showPyMessage('dq: ' + str(dq))
                    
                    lyr_cim = lyr.getDefinition('V2')
                    cim_ft = lyr_cim.featureTable
                    for dfc in cim_ft.definitionFilterChoices:
                        if dfc.name == 'MapNameDefQueryPython':
                            dfc.definitionExpression = dq
                        else:
                            cim_ft.definitionFilterChoices.remove(dfc)
                        
                    cim_ft.definitionExpression = dq
                    cim_ft.definitionExpressionName = "MapNameDefQueryPython"
                    lyr.setDefinition(lyr_cim)

    for tbl in m.listTables():
        if debug: showPyMessage(tbl.name)
        if debug: showPyMessage(tbl.dataSource)
        fcName=''
        for prop in tbl.dataSource.split(','):
            if prop[0:8] == 'Dataset=':
                fcName = prop.replace('Dataset=','')
        if debug: showPyMessage(fcName)

        if fcName.lower().find('gems') > -1 and mapfldname in [f.name for f in arcpy.ListFields(tbl.name,'*','String')]: 
            showPyMessage('Setting Defintion Query on ' + fcName)
            #--clears any mapname from dq----------
            dq = tbl.definitionQuery
            if debug: showPyMessage('dq0: ' + str(dq))
            dq = dq.replace('AND','And')
            if debug: showPyMessage('dq1: ' + str(dq))
            
            srchstr = dq[dq.find(mapfldname + " = '"):dq.find("'",dq.find(mapfldname + " = '")+(len(mapfldname + " = '")))+1]
            if srchstr != "'" and len(srchstr)>0:
                dq = dq.replace(" And " + srchstr, "")
                dq = dq.replace(srchstr + " And ", "")
                dq = dq.replace(srchstr, "")
            if debug: showPyMessage('dq2: ' + str(dq))
            
            #sets new definition query
            if clear == "true":
                dq = dq.replace(" And " + mapfldname + " = '" + mapname + "'", "")
                dq = dq.replace(mapfldname + " = '" + mapname + "'" + " And ", "")
                dq = dq.replace(mapfldname + " = '" + mapname + "'", "")
            elif clear == "false":
                if len((dq).strip())==0:
                    dq = mapfldname + " = '" + mapname + "'"
                else:
                    if mapfldname + " = '" + mapname + "'" not in dq:
                        dq = dq + " And " + mapfldname + " = '" + mapname + "'"
            if debug: showPyMessage('dq3: ' + str(dq))
            
            if (mapfldname and drawfldname) in [f.name for f in arcpy.ListFields(tbl.name,'*','String')]:
                if draw == "true":
                    if drawfldname + " = 'Yes'" not in dq:
                        if len((dq).strip())==0:
                            dq = dq + drawfldname + " = 'Yes'"
                        else:
                            dq = dq + " And " + drawfldname + " = 'Yes'"
                elif draw == "false":
                    dq = dq.replace(" And " + drawfldname + " = 'Yes'", "")
                    dq = dq.replace(drawfldname + " = 'Yes' And ", "")
                    dq = dq.replace(drawfldname + " = 'Yes'", "")
            if debug: showPyMessage('dq4: ' + str(dq))
            
            if debug: showPyMessage('dq: ' + str(dq))
            
            tbl_cim = tbl.getDefinition('V2')
            for dfc in tbl_cim.definitionFilterChoices:
                if dfc.name == 'MapNameDefQueryPython':
                    dfc.definitionExpression = dq
                else:
                    tbl_cim.definitionFilterChoices.remove(dfc)
                
            tbl_cim.definitionExpression = dq
            tbl_cim.definitionExpressionName = "MapNameDefQueryPython"
            tbl.setDefinition(tbl_cim)

  
if __name__ == '__main__':
    mapname = arcpy.GetParameterAsText(1) #sys.argv[1]   #Map Name
    clear = arcpy.GetParameterAsText(2) #sys.argv[2]   #Clear Option
    draw = arcpy.GetParameterAsText(3) #sys.argv[3]   #Set DrawOnMap to Yes
    SetDefQuery(mapname,clear,draw)
    
 
#-------------------validation script----------
import arcpy
class ToolValidator(object):
  """Class for validating a tool's parameter values and controlling
  the behavior of the tool's dialog."""

  def __init__(self):
    """Setup arcpy and the list of tool parameters."""
    self.params = arcpy.GetParameterInfo()

  def initializeParameters(self):
    """Refine the properties of a tool's parameters.  This method is
    called when the tool is opened."""
    schemaList = []
    for row in arcpy.da.SearchCursor(r'C:\GeMS_Coop\GeMS_Data_LOCAL.sde\GeMS_Data.dbo.GeMS_Schemas',['SCHEMA']):
      schemaList.append(row[0])
    self.params[1].filter.list = sorted(set(schemaList))
    return

  def updateParameters(self):
    """Modify the values and properties of parameters before internal
    validation is performed.  This method is called whenever a parameter
    has been changed."""
    mapList = []
    #for row in arcpy.da.SearchCursor(r'C:\GeMS_Coop\GeMS_Data_LOCAL.sde\GeMS_Data.dbo.GeMS_Domain_MapNames',['code'],'"Schema" = ' + "'" + self.params[0].value + "'"):
    for row in arcpy.da.SearchCursor(r'C:\GeMS_Coop\GeMS_Data_LOCAL.sde\GeMS_Data.' + self.params[0].value + '.Domain_MapName',['code']):
      mapList.append(row[0])
    self.params[1].filter.list = sorted(set(mapList))    
    return

  def updateMessages(self):
    """Modify the messages created by internal validation for each tool
    parameter.  This method is called after internal validation."""
    return
