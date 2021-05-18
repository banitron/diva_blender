# ------------------------------------------------------------
#           PLEASE READ - I CAN'T PROVIDE SUPPORT
# ------------------------------------------------------------

# Project Diva A3DA Importer v0.01b for Blender 2.8.x onwards
#     A3DA support is limited - FT and DT is best.
#     Cameras and object animations are supported, but are
#     not setup exactly like the game - eg you won't see
#     looping stage animations. Interpolation isn't perfect.
#
#     For using anything related to stages, import from
#     MikuMikuMoving first as a DAE. Consider converting
#     binary A3DAs to text (FT or DT) since there is better
#     compatibility. Stage morphs require you to manually
#     setup the morph targets on the main object (see code
#     to understand this). X cameras work fine as-is.
#     Bone animations will not be supported through this
#     script - find something for Noesis or anything with
#     access to bone matrices.
#     
#     If a file doesn't load, try contacting me but I might
#     not be able to help. This script is a few years old
#     at this point, so I don't even know what I wrote :/


# ------------------------------------------------------------
#                         CREDITS
# ------------------------------------------------------------
# Script (old, don't judge)   - banitron (me, deviantArt)
# Interpolation equation      - minmode

# Thanks to anyone who have used my motions over the years <3
# Feel free to edit. Please credit if you use this code.


# ------------------------------------------------------------
#                        HOW TO USE
# ------------------------------------------------------------
# If this is your first time running the script, open the
# Blender console and watch the output for any messages.
# This script will attempt to automatically install
# requirements to your Blender Python. This only works on
# Windows, so read the REQUIREMENTS section to get this
# working on other platforms. This will cause Blender to
# pause while treelib is being downloaded and installed.
#
# If you're trying to apply a stage or object anim, import
# the item in from MikuMikuModel as a DAE first and then run
# this script; no need to do this for cameras. A popup should
# then appear. Find your A3DA of choice to apply to all
# available objects.
#
# If no popup appears, treelib is not installed correctly.
# You may need to do this manually - see below.


# ------------------------------------------------------------
#               THIS SCRIPT HAS REQUIREMENTS
# ------------------------------------------------------------
# "treelib" is a required module for parsing the A3DAs.
# The script will attempt to automatically install this - 
#     this only works if you are on Windows.
#
# If this fails, go into your Blender install directory,
#     and then into the python/bin directory.
# In a command line, do (for Windows, but adjust as needed)
#
# python.exe -m ensurepip
# python.exe -m pip install treelib





# ------------------------------------------------------------
#            SCRIPT BELOW - MODIFY WITH CAUTION
# ------------------------------------------------------------

import sys, bpy, math, traceback
from numpy import frombuffer
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from os import walk, getcwd, system
from os import name as OS_NAME

canRun = True

try:
    from treelib import Tree
except ImportError:
    print("Detected treelib is missing!")
    
    if OS_NAME == "nt":
        print("\tAttempting to install treelib...")
        pathPython = None

        for path in walk(getcwd()):
            if "python.exe" in path[-1]:
                pathPython = path[0]
                break

        if pathPython != None:
            system('cd ' + pathPython + " & python.exe -m ensurepip & python.exe -m pip install treelib")
        
        try:
            from treelib import Tree
        except ImportError:
            print("\tCould not install treelib successfully - quitting!")
            canRun = False
    else:
        canRun = False

masterCollectionName = "Collection" # This is the target for script. If this is missing, you'll get an error
scaleTime = 1
scalePos = 1

def getChildren(ob):
    child = []
    for obj in bpy.data.objects:
        if obj.parent == ob:
            child.append(obj)
    return child

def getDuplicateSafeName(name):
    if bpy.data.objects.find(name) != -1:
        dupIndex = 1
        while True:
            if bpy.data.objects.find(name + "_" + str(dupIndex)) == -1:
                return name + "_" + str(dupIndex)
            dupIndex += 1
    return name

def addToCollection(tarCollection, object):
    # Add spawned object reference to collection
    for coll in bpy.data.collections:
        if object.name in coll.objects.keys():
            coll.objects.unlink(object)
    
    if object.name in bpy.context.scene.collection.objects.keys():
        bpy.context.scene.collection.objects.unlink(object)
            
    tarCollection.objects.link(object)

def createNewCollection(name):
    # Create a new collection and append it to the root collection
    if name in bpy.data.collections.keys():
        dupIndex = 1
        while True:
            if (name + "_" + str(dupIndex)) not in bpy.data.collections.keys():
                newCollection = bpy.data.collections.new(name + "_" + str(dupIndex))
                break
            dupIndex += 1
    else:
        newCollection = bpy.data.collections.new(name)
    bpy.data.collections[masterCollectionName].children.link(newCollection)
    return newCollection
    
def applyTransformations(tarObject, groupTrans):
    if len(groupTrans) > 0:
        transformationMapDict = {0:0, 1:2, 2:1}
        transformationPropDict = {"scale":"scale",
                                  "rot":"rotation_euler",
                                  "trans":"location"}
        transformationScaleDict = {0:1, 1:1, 2:1}
        
        for group in groupTrans:
            
            if group.name in transformationPropDict.keys():
                
                if group.name != "scale":
                    transformationScaleDict[1] = -1
                
                tracks = [group.x, group.y, group.z]
                for indexTrack in range(3):
                    if tracks[indexTrack] != None:
                        tracks[indexTrack].sortFrames()
                        tracks[indexTrack].bakeInterpolation()
                        # If there is animation data for this channel
                        for newFrame in tracks[indexTrack].frames:
                            if newFrame.value != None:
                                if transformationPropDict[group.name] == "scale":
                                    tarObject.scale[transformationMapDict[indexTrack]] = newFrame.value * transformationScaleDict[transformationMapDict[indexTrack]]
                            
                                if transformationPropDict[group.name] == "rotation_euler":
                                    tarObject.rotation_euler[transformationMapDict[indexTrack]] = newFrame.value * transformationScaleDict[transformationMapDict[indexTrack]]
                            
                                if transformationPropDict[group.name] == "location":
                                    tarObject.location[transformationMapDict[indexTrack]] = newFrame.value * transformationScaleDict[transformationMapDict[indexTrack]]
                            
                                tarObject.keyframe_insert(data_path=transformationPropDict[group.name], index = transformationMapDict[indexTrack], frame=newFrame.time * scaleTime)

# A3DALib starts here

def splitLineUntilValue(line):
    line = line.split(".")
    endIndex = 0
    for section in range(len(line)):
        if "=" in line[section]:
            break
        else:
            endIndex += 1
    line = line[0:endIndex] + [".".join(line[endIndex:])[:-1]]
    return [line[0:-1]+[line[-1].split("=")[0]], line[-1].split("=")[-1]]

def decodeAnimationBranch(branch):                                 # Function fully decodes an animated property branch
    tempTrack = A3daKeyframedTrack()
    tempTrack.nameProperty = branch.root.split(".")[-1]
    nodeChildren = branch.children(branch.root)
    if len(nodeChildren) > 1:
        for child in nodeChildren:
            a3daIdentifier = child.identifier.split(".")[-1]
            nodeProperties = branch.children(child.identifier)
            
            if a3daIdentifier == "type":
                if branch.contains(branch.root + ".value"):         # Single frame of animation
                    tempTrack.frames.append(A3daKeyframe(0, float(branch.get_node(branch.root + ".value").data), 1))
                else:                                               # Affects entire track
                    tempTrack.type = int(child.data)

            elif a3daIdentifier == "max":
                tempTrack.relativeEndFrame = int(child.data)
            
            elif a3daIdentifier == "raw_data":
                if (branch.contains(child.identifier + ".value_list") and branch.contains(branch.root + ".raw_data_key_type")):
                    listValueFrame = branch.get_node(child.identifier + ".value_list").data.split(",")
                    listValueType = int(branch.get_node(branch.root + ".raw_data_key_type").data)

                    for indexFrame in range(int(len(listValueFrame) / (listValueType + 1))):
                        frameStart = (listValueType + 1) * indexFrame
                        tempFrame = A3daKeyframe(int(listValueFrame[frameStart]), None, listValueType)
                        if tempFrame.type == 0:
                            tempFrame.value = 0
                        elif tempFrame.type > 0:
                            tempFrame.value = float(listValueFrame[frameStart + 1])
                        if tempFrame.type == 2:
                            tempFrame.slopeOut = float(listValueFrame[frameStart + 2])
                        if tempFrame.type == 3:
                            tempFrame.slopeIn = float(listValueFrame[frameStart + 2])
                            tempFrame.slopeOut = float(listValueFrame[frameStart + 3])
                        tempTrack.frames.append(tempFrame)
                else:
                    print("\t  Nodes not mapped for unpacking. Skipping...")
            
            elif a3daIdentifier == "key":
                for nodeFrame in nodeProperties:
                    nodeData = branch.children(nodeFrame.identifier)[0]
                    if nodeData.data[0] == "(":
                        valueFrame = nodeData.data[1:-1].split(",")
                    else:
                        valueFrame = [nodeData.data]
                    tempFrame = A3daKeyframe(int(valueFrame[0]), None, len(valueFrame) - 1)
                    if tempFrame.type == 0:
                        tempFrame.value = 0
                    elif tempFrame.type > 0:
                        tempFrame.value = float(valueFrame[1])
                    if tempFrame.type > 1:
                        tempFrame.slopeOut = float(valueFrame[-1])
                    if tempFrame.type > 2:
                        tempFrame.slopeIn = float(valueFrame[2])
                    tempTrack.frames.append(tempFrame)

            elif a3daIdentifier not in ["raw_data_key_type", "value"]:
                print("\t\t\t\t\t\tIdentifier not implemented: " + a3daIdentifier)

    if len(tempTrack.frames) > 0:
        return [True, tempTrack]
    else:
        return [False, tempTrack]

def decodeFromTripletGroup(branch):
    tempGroup = A3daGroupedTransformation()
    tempGroup.name = branch.get_node(branch.root).tag
    for axis in ["x","y","z"]:
        if branch.contains(branch.root  + "." + axis):
            tempFrame = decodeAnimationBranch(branch.subtree(branch.root  + "." + axis))
            if tempFrame[0]:
                if axis == "x":
                    tempGroup.x = tempFrame[1]
                elif axis == "y":
                    tempGroup.y = tempFrame[1]
                else:
                    tempGroup.z = tempFrame[1]
    if tempGroup.y != None or tempGroup.x != None or tempGroup.z != None:
        return [True, tempGroup]
    else:
        return [False, tempGroup]

class A3daKeyframe():
    def __init__(self, time, value, a3daType):
        self.type = a3daType
        self.time = time
        self.value = value
        self.slopeIn = None
        self.slopeOut = None
    def __str__(self):
        return ("Frame\t" + str(self.time) + "\t" + str(self.value))

class A3daKeyframedTrack():
    def __init__(self):
        self.nameProperty = ""
        self.type = None
        self.relativeEndFrame = 0 # Distance from scene beginning to end
        self.frames = []

    def __str__(self):
        output = self.nameProperty + "\n"
        for frame in self.frames:
            output += str(frame.time) + "," + str(frame.value) + "\n"
        return output
    
    def bakeInterpolation(self):
        self.sortFrames()
        interFrames = []
        for frameIndex in range(len(self.frames) - 1):
            deltaFrame = self.frames[frameIndex + 1].time - self.frames[frameIndex].time
            
            if deltaFrame < 2 or (self.frames[frameIndex + 1].type < 1 or self.frames[frameIndex].type < 1) or (self.frames[frameIndex].type == 1 and self.frames[frameIndex + 1].type == 1):
                pass
            else:
                if self.frames[frameIndex].type > 1:
                    slopeOut = self.frames[frameIndex].slopeOut
                else:
                    slopeOut = (self.frames[frameIndex + 1].value - self.frames[frameIndex].value) / deltaFrame
                    
                if self.frames[frameIndex + 1].type == 3:
                    slopeIn = self.frames[frameIndex + 1].slopeIn
                elif self.frames[frameIndex + 1].type == 2:
                    slopeIn = self.frames[frameIndex + 1].slopeOut
                else:
                    if frameIndex + 2 < len(self.frames) and (self.frames[frameIndex + 2].time - self.frames[frameIndex + 1].time) > 0:
                        slopeIn = ((self.frames[frameIndex + 2].value - self.frames[frameIndex + 1].value) /
                                   (self.frames[frameIndex + 2].time - self.frames[frameIndex + 1].time))
                    else:
                        slopeIn = slopeOut

                for interFrameIndex in range(deltaFrame - 1):
                    factor = (interFrameIndex + 1) / deltaFrame
                    interValue = (((factor - 1) * 2 - 1) * (factor * factor) * (self.frames[frameIndex].value - self.frames[frameIndex + 1].value) +
                                  ((factor - 1) * slopeOut + factor * slopeIn) *
                                  (factor - 1) * (interFrameIndex + 1) + self.frames[frameIndex].value)
                    interFrames.append(A3daKeyframe(self.frames[frameIndex].time + interFrameIndex + 1, interValue, 2))

        if len(interFrames) > 0:
            self.frames.extend(interFrames)
            self.sortFrames()
            return True
        return False
    
    def sortFrames(self):
        self.frames.sort(key=lambda x: x.time, reverse=False)
    
class A3daGroupedTransformation(object):
    def __init__(self):
        self.name = ""
        self.x = None
        self.y = None
        self.z = None
    
    def bakeInterpolation(self):
        if self.x != None:
            self.x.bakeInterpolation()
        if self.y != None:
            self.y.bakeInterpolation()
        if self.z != None:
            self.z.bakeInterpolation()
    
    def __str__(self):
        output = self.name + "\n"
        for track in [self.x, self.y, self.z]:
            if track != None:
                output += str(track)
        return output

class A3daCurve():
    def __init__(self):
        self.name = None
        self.trackCv = None
        self.typeFx = None
    def decodeFromInstanceBranch(self, branch):
        if branch.contains(branch.root + ".cv"):
            self.trackCv = decodeAnimationBranch(branch.subtree(branch.root + ".cv"))[1]
        if branch.contains(branch.root + ".name"):
            self.name = branch.get_node(branch.root + ".name").data
        if branch.contains(branch.root + ".ep_type_post"):
            self.typeFx = branch.get_node(branch.root + ".ep_type_post").data

class A3daNode():
    def __init__(self):
        self.name = None
        self.id = None
        self.parentTransformations = []
        self.trackVisibility = None
        self.instanceId = None
    
    def __str__(self):
        output = str(self.name) + ","
        if self.id == None:
            output += "-1,"
        else:
            output += str(self.id) + ","
        if self.instanceId != None:
            output += str(self.instanceId) + "\n"
        else:
            output += "-1\n"
        for trans in self.parentTransformations:
            output += str(self.parentTransformations) + "\n"
        if self.trackVisibility != None:
            output += str(self.trackVisibility) + "\n"
        return output
    
    def blenderLoad(self):
        print("No loader: " + self.name)

class A3daLight(A3daNode):
    def __init__(self):
        A3daNode.__init__(self)
        self.rootTransformations = []
        self.interestTransformations = []
        self.type = ""

        self.colourAmbient = []
        self.colourDiffuse = []
        self.colourIncandescence = []
        self.colourSpecular = []

    def decodeFromInstanceBranch(self, branch):
        print("\tExtracting light...")

        self.name = branch.get_node(branch.root + ".name").data
        self.id = branch.get_node(branch.root + ".id").data
        self.type = branch.get_node(branch.root + ".type").data
        
        if branch.contains(branch.root + ".Ambient") and branch.get_node(branch.root + ".Ambient").data == "true":
            print("\t\tGrabbing ambient colour animation...")
            self.colourAmbient = [decodeAnimationBranch(branch.subtree(branch.root + ".Ambient.r"))[1],
                                  decodeAnimationBranch(branch.subtree(branch.root + ".Ambient.g"))[1],
                                  decodeAnimationBranch(branch.subtree(branch.root + ".Ambient.b"))[1]]

        if branch.contains(branch.root + ".Diffuse") and branch.get_node(branch.root + ".Diffuse").data == "true":
            print("\t\tGrabbing diffuse colour animation...")
            self.colourDiffuse = [decodeAnimationBranch(branch.subtree(branch.root + ".Diffuse.r"))[1],
                                  decodeAnimationBranch(branch.subtree(branch.root + ".Diffuse.g"))[1],
                                  decodeAnimationBranch(branch.subtree(branch.root + ".Diffuse.b"))[1]]

        if branch.contains(branch.root + ".Incandescence") and branch.get_node(branch.root + ".Incandescence").data == "true":
            print("\t\tGrabbing incandescence colour animation...")
            self.colourIncandescence = [decodeAnimationBranch(branch.subtree(branch.root + ".Incandescence.r"))[1],
                                        decodeAnimationBranch(branch.subtree(branch.root + ".Incandescence.g"))[1],
                                        decodeAnimationBranch(branch.subtree(branch.root + ".Incandescence.b"))[1]]

        if branch.contains(branch.root + ".Specular") and branch.get_node(branch.root + ".Specular").data == "true":
            print("\t\tGrabbing specular colour animation...")
            self.colourSpecular = [decodeAnimationBranch(branch.subtree(branch.root + ".Specular.r"))[1],
                                   decodeAnimationBranch(branch.subtree(branch.root + ".Specular.g"))[1],
                                   decodeAnimationBranch(branch.subtree(branch.root + ".Specular.b"))[1]]

        for transformation in ["trans", "rot", "scale"]:
            for rootGroup in ["position.", "spot_direction."]:
                tempGroup = decodeFromTripletGroup(branch.subtree(branch.root + "." + rootGroup + transformation))
                if tempGroup[0]:
                    if rootGroup == "position.":
                        self.rootTransformations.append(tempGroup[1])
                    else:
                        self.interestTransformations.append(tempGroup[1])
                else:
                    print("\t\t\t" + "Failed! " + rootGroup + transformation)

class A3daCamera(A3daNode):
    def __init__(self):
        A3daNode.__init__(self)
        self.viewpointTransformations =  []
        self.interestTransformations = []
        
        self.trackRoll = None
        self.trackFov = None
        self.isFovHorizontal = False
        self.fovAspect = 0
        
    def decodeFromInstanceBranch(self, branch):
        print("\tExtracting camera...")

        self.fovAspect = float(branch.get_node(branch.root + ".view_point.aspect").data)
        self.trackFov = decodeAnimationBranch(branch.subtree(branch.root + ".view_point.fov"))[1]
        self.trackRoll = decodeAnimationBranch(branch.subtree(branch.root + ".view_point.roll"))[1]
        self.trackVisibility = decodeAnimationBranch(branch.subtree(branch.root + ".view_point.visibility"))[1]
        self.isFovHorizontal = [False, True][int(branch.get_node(branch.root + ".view_point.fov_is_horizontal").data)]

        for transformation in ["trans", "rot", "scale"]:
            for rootGroup in ["view_point.", "interest.", ""]:
                tempGroup = decodeFromTripletGroup(branch.subtree(branch.root + "." + rootGroup + transformation))
                if tempGroup[0]:
                    if rootGroup == "view_point.":
                        self.viewpointTransformations.append(tempGroup[1])
                    elif rootGroup == "interest.":
                        self.interestTransformations.append(tempGroup[1])
                    else:
                        self.parentTransformations.append(tempGroup[1])
                        
    def blenderLoad(self):
        camCo = createNewCollection("A3DA Camera")
        
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=[0,0,0])
        rootObj = bpy.context.object
        rootObj.name = getDuplicateSafeName("Camera Root")
        addToCollection(camCo, rootObj)
        
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=[0,0,0])
        posObj = bpy.context.object
        posObj.parent = rootObj
        posObj.name = getDuplicateSafeName("Camera Position")
        addToCollection(camCo, posObj)
            
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=[0,0,0])
        dirObj = bpy.context.object
        dirObj.parent = rootObj
        dirObj.name = getDuplicateSafeName("Camera Direction")
        addToCollection(camCo, dirObj)
        
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=[0,0,0])
        trkObj = bpy.context.object
        trkObj.parent = posObj
        trkObj.name = getDuplicateSafeName("Camera Constraint")
        addToCollection(camCo, trkObj)
        
        ftCamConstraint = trkObj.constraints.new("TRACK_TO")
        ftCamConstraint.target = dirObj
        ftCamConstraint.track_axis = "TRACK_NEGATIVE_Z"
        ftCamConstraint.up_axis = "UP_Y"
        
        bpy.ops.object.camera_add(location=(0,0,0), rotation=(0,0,0))
        ftCam = bpy.context.object
        ftCam.parent = trkObj
        ftCam.name = "Camera"
        addToCollection(camCo, ftCam)
        
        self.trackRoll.sortFrames()
        self.trackRoll.bakeInterpolation()
        
        for spawnFrame in self.trackRoll.frames:
            if spawnFrame.type > 0:
                ftCam.rotation_euler[2] = spawnFrame.value
                ftCam.keyframe_insert(data_path="rotation_euler", index=2, frame=spawnFrame.time * scaleTime)
        
        applyTransformations(rootObj, self.parentTransformations)
        applyTransformations(dirObj, self.interestTransformations)
        applyTransformations(posObj, self.viewpointTransformations)
        
        ftCam = ftCam.data
        
        self.trackFov.sortFrames()
        self.trackFov.bakeInterpolation()
        
        for spawnFrame in self.trackFov.frames:
            if spawnFrame.type > 0:
                ftCam.lens = ftCam.sensor_width/2 / math.tan(spawnFrame.value/2)
                ftCam.keyframe_insert(data_path = "lens", frame = spawnFrame.time)

class A3daGeneralObject(A3daNode):
    def __init__(self):
        A3daNode.__init__(self)
        self.parentName = None
        self.parentId = None
        self.uid = None
        self.morphName = None
        self.morphOffset = None
        self.textureTransformations = []
        
    def decodeFromInstanceBranch(self, branch):
        print("\tDecoding object...")
        for child in branch.children(branch.root):
            if child.tag in ["rot", "scale", "trans"]:
                print("\t\t" + child.tag)
                tempGroup = decodeFromTripletGroup(branch.subtree(child.identifier))
                if tempGroup[0]:
                    self.parentTransformations.append(tempGroup[1])

            elif child.tag == "tex_transform":
                for texChild in branch.children(child.identifier):
                    tempTexName = branch.get_node(texChild.identifier + ".name").data
                    if branch.contains(texChild.identifier + ".translateFrameU"):
                        if branch.get_node(texChild.identifier + ".translateFrameU").data == "true":
                            self.textureTransformations.append(decodeAnimationBranch(branch.subtree(texChild.identifier + ".translateFrameU"))[1])
                            self.textureTransformations[-1].nameProperty += "." + tempTexName
                    if branch.contains(texChild.identifier + ".translateFrameV"):
                        if branch.get_node(texChild.identifier + ".translateFrameV").data == "true":
                            self.textureTransformations.append(decodeAnimationBranch(branch.subtree(texChild.identifier + ".translateFrameV"))[1])
                            self.textureTransformations[-1].nameProperty += "." + tempTexName

            elif child.tag == "morph":
                self.morphName = child.data
            elif child.tag == "morph_offset":
                self.morphOffset = int(child.data)
            elif child.tag == "visibility":
                self.trackVisibility = decodeAnimationBranch(branch.subtree(child.identifier))[1]
            elif child.tag == "name":
                self.name = child.data
            elif child.tag == "uid_name":
                self.uid = child.data
            elif child.tag == "parent_name":
                self.parentName = child.data
            elif child.tag == "parent":
                if child.data != "-1":
                    self.parentId = int(child.data)
            else:
                print("\t\t\tData track unsupported: " + child.tag)
    
    def blenderLoad(self, targetColl, sourceColl, crvObjDb):
        if self.parentName != None or self.parentId != None:
            print("Need to set parent!")
        
        if self.uid != None:
            if self.uid in sourceColl.objects.keys():
                tarObject = sourceColl.objects[self.uid]
            else:
                # Spawn an empty if the object does not exist
                bpy.ops.object.empty_add(type="PLAIN_AXES", location=[0,0,0])
                tarObject = bpy.context.object
                tarObject.name = self.uid
                
            tarChildren = getChildren(tarObject)
            newObject = tarObject.copy()
            newObject.name = getDuplicateSafeName(self.uid + "_MASTER")
            addToCollection(targetColl, newObject)
            for child in tarChildren:
                childCopy = child.copy()
                childCopy.name = getDuplicateSafeName(child.name)
                childCopy.parent = newObject
                addToCollection(targetColl, childCopy)
            
            bpy.ops.object.empty_add(type="PLAIN_AXES", location=newObject.location)
            ctlObj = bpy.context.object
            ctlObj.name = getDuplicateSafeName(self.uid + "_CONTROLLER")
            addToCollection(targetColl, ctlObj)
            newObject.parent = ctlObj
            newObject.location = [0,0,0]
            
            if self.parentTransformations != []:
                applyTransformations(ctlObj, self.parentTransformations)
                
            # Apply curve animations - experimental and requires prepreperation
            # Setup the morph targets and ensure that each morph is relative to the last
            if self.morphName != None:
                print("Registered morph on " + newObject.name)
                if self.morphName in crvObjDb.keys():
                    print("\tMorph found! Applying...")
                    targetCurve = crvObjDb[self.morphName]
                    #targetCurve.trackCv.sortFrames()
                    #targetCurve.trackCv.bakeInterpolation()
                    
                    targetMeshes = []
                    targetMeshesMaxShape = None
                    targetMeshesMaxShapeFailure = False
                    
                    if len(ctlObj.children) == 1:
                        for targetMorphObject in ctlObj.children[0].children:
                            if targetMorphObject.type == "MESH" and targetMorphObject.data.shape_keys != None:
                                targetMeshes.append(targetMorphObject.data.shape_keys.key_blocks)
                                if targetMeshesMaxShape == None:
                                    targetMeshesMaxShape = len(targetMorphObject.data.shape_keys.key_blocks.keys())
                                elif len(targetMorphObject.data.shape_keys.key_blocks.keys()) != targetMeshesMaxShape:
                                    print("\tShape keys not consistent across connected meshes! Cannot continue.")
                                    targetMeshesMaxShapeFailure = True
                                    break

                        if targetMeshesMaxShape == None:
                            targetMeshesMaxShapeFailure = True
                        
                        if not(targetMeshesMaxShapeFailure):
                            for cvFrame in targetCurve.trackCv.frames:
                                for morphIndex in range(1, targetMeshesMaxShape):
                                    if cvFrame.value < morphIndex and cvFrame.value > morphIndex - 1:
                                        # Morph is set to a value between here
                                        morphValue = cvFrame.value - (morphIndex - 1)
                                    if cvFrame.value >= morphIndex:
                                        # Set morph index to 1
                                        morphValue = 1
                                    else:
                                        # Morph is disabled
                                        morphValue = 0
                                        
                                    for targetMesh in targetMeshes:
                                        targetMesh[targetMesh.keys()[morphIndex]].value = morphValue
                                        targetMesh[targetMesh.keys()[morphIndex]].keyframe_insert("value", frame=cvFrame.time)
                            print("\tSuccessfully applied!")
                    else:
                        print("Couldn't find target meshes!")
                else:
                    print("\tCurve doesn't exist!")
        else:
            print("No object reference set! \t" + str(self.uid))

class A3daDofController(A3daGeneralObject):
    def __init__(self):
        A3daGeneralObject.__init__(self)
    
    def blenderLoad(self):
        dofCo = createNewCollection("A3DA DOF Controller")
        
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=[0,0,0])
        dofObj = bpy.context.object
        dofObj.name = getDuplicateSafeName(self.name)
        dofObj.empty_display_type = "SPHERE"
        addToCollection(dofCo, dofObj)
        
        applyTransformations(dofObj, self.parentTransformations)

class A3daNodeGroup(A3daNode):
    def __init__(self):
        A3daNode.__init__(self)
        self.uid = None
        self.nodes = []
        self.jointOrient = [0,0,0]

    def decodeFromInstanceBranch(self, branch):
        self.name = branch.get_node(branch.root + ".name").data
        self.uid = branch.get_node(branch.root + ".uid_name").data

        for child in branch.children(branch.root + ".node"):
            if child.tag.isdigit():
                tempObj = A3daGeneralObject()
                tempObj.decodeFromInstanceBranch(branch.subtree(child.identifier))
                if int(child.tag) == 0:
                    self.nodes.append(tempObj)
                else:
                    if int(child.tag) < len(self.nodes):
                        self.nodes[int(child.tag)] = tempObj
                    else:
                        for fillerObj in range(int(child.tag) - len(self.nodes)):
                            self.nodes.append(None)
                        self.nodes.append(tempObj)
            else:
                print("Unknown grouped node: " + child.tag)
            
class A3daScene(object):
    def __init__(self):
        self.name = ""
        self.type = "DT"
        self.tree = None
        self.sceneObjects = []
        self.begin = None
        self.fps = None
        self.offset = 0
        self.duration = None

    def processDtContent(self, filename):
        lines = []
        with open(filename, 'r') as a3daText:
            if a3daText.readline() == "#A3DA__________\n":
                for line in a3daText:
                    lines.append(line)
        self.constructFromLines(lines)
        return True

    def f2ndFetchTrack(self, reader, trackOffset, binaryStartOffset, useHalfFloats=False):
        # Improvements: Migrate all a3da struct code to its own class to enable faster reading and writing of structs
        oldOffset = reader.tell()
        reader.seek(binaryStartOffset + trackOffset)
        trackType = int.from_bytes(reader.read(1), byteorder = 'little', signed = False)
        reader.seek(3, 1)
        frames = []
        trackMaxFrame = 0
        if trackType == 1:
            frames.append([None, frombuffer(reader.read(4), dtype='<f4')[0]])
            
        elif trackType > 1:
            trackStartFrame = frombuffer(reader.read(4), dtype='<f4')[0]
            trackMaxFrame = frombuffer(reader.read(4), dtype='<f4')[0]
            trackTotalFrames = int.from_bytes(reader.read(4), byteorder = 'little', signed = False)
            
            for frame in range(trackTotalFrames):
                if useHalfFloats:
                    frameData = [str(int.from_bytes(reader.read(2), byteorder = 'little')), str(float(frombuffer(reader.read(2), dtype='<f2')[0]))]
                else:
                    frameData = [str(int(frombuffer(reader.read(4), dtype='<f4')[0])), str(frombuffer(reader.read(4), dtype='<f4')[0])]

                for data in range(2):   # Regardless of track type, slopeIn and slopeOut are still given
                    frameData.append(str(frombuffer(reader.read(4), dtype='<f4')[0]))
                frames.append(frameData)
                
        reader.seek(oldOffset)
        return [frames, trackType, int(trackMaxFrame)]

    def addNodeIfDoesNotExist(self, name, uuidParent):
        if self.tree.contains(uuidParent + "." + name) == False:
            self.tree.create_node(name, uuidParent + '.' + name, parent=uuidParent)
    
    def processF2ndContent(self, reader):
        reader.seek(8)
        
        a3daContentOffset = int.from_bytes(reader.read(4), byteorder = 'little', signed = False)
        
        overrideCompression = False
        if a3daContentOffset == 64:
            # Known header, try to find the compression flag hack
            # Some files use the compression header without actually being compressed, one byte in
            #     the header can be used to differentiate the files which are actually correct
            reader.seek(51)
            if int.from_bytes(reader.read(1), byteorder = 'little') <= 1:
                overrideCompression = True
                
        reader.seek(a3daContentOffset)
        if reader.read(4) == b'#A3D':
            reader.seek(32, 1)
            a3daContentHeaderLength = int.from_bytes(reader.read(4), byteorder = 'big', signed = False)
            a3daContentLength = int.from_bytes(reader.read(4), byteorder = 'big', signed = False)
            reader.seek(8, 1)
            a3daContentWithHeaderLength = int.from_bytes(reader.read(4), byteorder = 'big', signed = False)
            a3daContentEofcOffset = int.from_bytes(reader.read(4), byteorder = 'big', signed = False)
            reader.seek(a3daContentOffset + a3daContentHeaderLength)

            a3dcText = reader.read(a3daContentLength).decode('ascii').split("\n")[0:-1]
            for lineIndex in range(len(a3dcText)):
                a3dcText[lineIndex] += "\n"
            self.constructFromLines(a3dcText)
            if not(overrideCompression) and self.tree.contains("root._.compress_f16") and self.tree.get_node("root._.compress_f16").data == "1":
                useCompressedFloats = True
            else:
                useCompressedFloats = False

            reader.seek(a3daContentOffset + a3daContentWithHeaderLength) # Binary starts here
            print("Populating tree with binary content...")
            axisMap = {0:"x", 1:"y", 2:"z"}

            for node in self.tree.leaves():
                if node.tag == "bin_offset":
                    if self.tree.get_node(node.bpointer).tag == "model_transform":
                        reader.seek(a3daContentOffset + a3daContentWithHeaderLength + int(node.data))
                        for offsetIndex in range(10):
                            trackData = self.f2ndFetchTrack(reader, int.from_bytes(reader.read(4), byteorder = 'little', signed = False), a3daContentOffset + a3daContentWithHeaderLength, useHalfFloats = useCompressedFloats)
                            if offsetIndex == 9:                # Visibility anim
                                a3daProp = "visibility"
                                a3daParent = self.tree.get_node(self.tree.get_node(node.bpointer).bpointer).identifier + "." + a3daProp
                                self.addNodeIfDoesNotExist(a3daProp, self.tree.get_node(self.tree.get_node(node.bpointer).bpointer).identifier)
                            else:
                                if offsetIndex >= 6:            # Location anim
                                    a3daProp = "trans"
                                elif offsetIndex >= 3:          # Rotation anim
                                    a3daProp = "rot"
                                else:                           # Scale
                                    a3daProp = "scale"
                                    
                                a3daParent = self.tree.get_node(self.tree.get_node(node.bpointer).bpointer).identifier + "." + a3daProp + "." + axisMap[offsetIndex % 3]
                                self.addNodeIfDoesNotExist(a3daProp, self.tree.get_node(self.tree.get_node(node.bpointer).bpointer).identifier)
                                self.addNodeIfDoesNotExist(axisMap[offsetIndex % 3], self.tree.get_node(self.tree.get_node(node.bpointer).bpointer).identifier + "." + a3daProp)
                            
                            self.tree.create_node("type", a3daParent + ".type", parent=a3daParent, data=str(trackData[1]))
                            if trackData[1] == 1:
                                self.tree.create_node("value", a3daParent + ".value", parent=a3daParent, data=str(trackData[0][0][1]))
                            elif trackData[1] > 1:
                                self.tree.create_node("max", a3daParent + ".max", parent=a3daParent, data=str(trackData[2]))
                                self.tree.create_node("key", a3daParent + ".key", parent=a3daParent)
                                for frameIndex in range(len(trackData[0])):
                                    self.tree.create_node(str(frameIndex), a3daParent + ".key." + str(frameIndex),
                                                          parent=a3daParent + ".key")
                                    self.tree.create_node("data", a3daParent + ".key." + str(frameIndex) + ".data",
                                                          parent=a3daParent + ".key." + str(frameIndex), data=("(" + ','.join(trackData[0][frameIndex]) + ")"))
                        self.tree.remove_node(node.bpointer)
                                
                    else:
                        trackData = self.f2ndFetchTrack(reader, int(node.data), a3daContentOffset + a3daContentWithHeaderLength, useHalfFloats = useCompressedFloats)
                        a3daParent = self.tree.get_node(node.bpointer).identifier

                        self.tree.create_node("type", a3daParent + ".type", parent=a3daParent, data=str(trackData[1]))
                        if trackData[1] == 1:
                            self.tree.create_node("value", a3daParent + ".value", parent=a3daParent, data=str(trackData[0][0][1]))
                        elif trackData[1] > 1:
                            self.tree.create_node("max", a3daParent + ".max", parent=a3daParent, data=str(trackData[2]))
                            self.tree.create_node("key", a3daParent + ".key", parent=a3daParent)
                            for frameIndex in range(len(trackData[0])):
                                self.tree.create_node(str(frameIndex), a3daParent + ".key." + str(frameIndex),
                                                      parent=a3daParent + ".key")
                                self.tree.create_node("data", a3daParent + ".key." + str(frameIndex) + ".data",
                                                      parent=a3daParent + ".key." + str(frameIndex), data=("(" + ','.join(trackData[0][frameIndex]) + ")"))
                        self.tree.remove_node(node.identifier)
        else:
            print("Version not supported!")
            return False
    
    def load(self, filename):
        with open(filename, 'rb') as a3daBinary:

            magic = a3daBinary.read(4)
            
            if magic == b'#A3D':
                if not(self.processDtContent(filename)):
                    return False
            elif magic == b'A3DA':
                if not(self.processF2ndContent(a3daBinary)):
                    return False
                self.type = "F2nd"
            else:
                print("Format unsupported!")
                return False

        return True
    
    def createNewTree(self, lines):
        self.tree = Tree()
        self.tree.create_node("A3DA", "root")
        for line in lines:
            if line[0] != "#":
                if "length" not in line and ("list" not in line or ("material_list" in line or "value_list" in line)):
                    line = splitLineUntilValue(line)
                    if not(line[0][-1] == "type" and "key" in line[0]):
                        for treeBuilder in range(len(line[0])):
                            if self.tree.contains("root." + '.'.join(line[0][0:treeBuilder + 1])) == False:
                                if treeBuilder == 0:
                                    uuidParent = "root"
                                else:
                                    uuidParent = "root." + '.'.join(line[0][0:treeBuilder])

                                if treeBuilder != len(line[0]) - 1:
                                    self.tree.create_node(line[0][treeBuilder], "root." + '.'.join(line[0][0:treeBuilder + 1]), parent=uuidParent)
                                else:
                                    self.tree.create_node(line[0][treeBuilder], "root." + '.'.join(line[0][0:treeBuilder + 1]), parent=uuidParent, data=line[1])
    
    def constructFromLines(self, lines):            # This method is non-lossy but simplifies nodes as much as possible
        print("Constructing A3DA nodes from cached lines...")
        self.createNewTree(lines)
        print("Finished constructing node branches.")

    def appendToScene(self, tag, branch, instanceId = None):
        if tag == "camera_root":
            self.sceneObjects.append(A3daCamera())
        elif tag == "dof":
            self.sceneObjects.append(A3daDofController())
        elif tag == "object":
            self.sceneObjects.append(A3daGeneralObject())
        elif tag == "curve":
            self.sceneObjects.append(A3daCurve())
        elif tag == "light":
            self.sceneObjects.append(A3daLight())
        elif tag == "objhrc":
            self.sceneObjects.append(A3daNodeGroup())
        else:
            print("Unknown object: " + tag)
            self.sceneObjects.append(A3daGeneralObject())
        self.sceneObjects[-1].decodeFromInstanceBranch(branch)
        self.sceneObjects[-1].instanceId = instanceId
    
    def decodeTree(self):           # Minimally-lossy, all important data is preserved for importing or reconstruction
        for child in self.tree.children("root"):
            if child.tag == "play_control":
                self.begin = int(self.tree.get_node("root.play_control.begin").data)
                self.fps = int(self.tree.get_node("root.play_control.fps").data)
                
                if self.tree.contains("root.play_control.offset"):
                    self.offset = int(self.tree.get_node("root.play_control.offset").data)
                    
                self.duration = int(self.tree.get_node("root.play_control.size").data)
                print("\tUpdated scene details!")
            elif child.tag in ["_"]:
                pass        # Objects with underscores are disabled
            else:
                if len(child.tag) > 5 and child.tag[-5:] == "_list" and child.tag != "material_list":   
                    pass    # Skip list objects as they are exactly what they sound like
                else:
                    print("\n" + child.tag)
                    if self.tree.children(child.identifier)[0].tag.isdigit() and child.tag != "material_list":
                        for instanceChild in self.tree.children(child.identifier):
                            self.appendToScene(child.tag, self.tree.subtree(instanceChild.identifier), instanceId = int(self.tree.children(child.identifier)[0].tag))
                    else:
                        self.appendToScene(child.tag, self.tree.subtree(child.identifier), instanceId = None)
                        
    def blenderLoad(self):
        if self.offset != None:
            scnOffset = self.offset
        else:
            scnOffset = 0
            
        bpy.context.scene.frame_start = self.begin + scnOffset
        bpy.context.scene.frame_end = self.duration + scnOffset
        
        bpy.context.scene.render.fps = self.fps
        bpy.context.scene.render.fps_base = 1
        
        bufferGenObj = []
        crvObjDb = {}
        
        for obj in self.sceneObjects:
            if type(obj) == A3daCurve:
                crvObjDb[obj.name] = obj
            elif type(obj) != A3daGeneralObject:
                obj.blenderLoad()
            else:
                bufferGenObj.append(obj)
        
        targetColl = None
        if len(bufferGenObj) > 0:
            targetColl = createNewCollection("A3DA Scene")
            sourceColl = bpy.data.collections[masterCollectionName]
            for obj in bufferGenObj:
                # Additionally pass the start and end frame to the objects to hide at the end of takes
                obj.blenderLoad(targetColl, sourceColl, crvObjDb)
        
        print("Import complete!")

class ImportA3da(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "import_test.some_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import A3DA"

    filter_glob = StringProperty(
        default="*.a3da",
        options={'HIDDEN'},
        )
        
    def execute(self, context):
        try:
            debug = A3daScene()
            debug.load(self.filepath)     # A3DA for input
            debug.decodeTree()
            debug.blenderLoad()
        except:
            traceback.print_exc()
        unregister()
        return{'FINISHED'}

def register():
    bpy.utils.register_class(ImportA3da)

def unregister():
    bpy.utils.unregister_class(ImportA3da)

if canRun:
    register()
    bpy.ops.import_test.some_data('INVOKE_DEFAULT')
else:
    print("\tScript could not execute due to missing treelib!")