# ------------------------------------------------------------
#           PLEASE READ - I CAN'T PROVIDE SUPPORT
# ------------------------------------------------------------

# A3DA to MMD Camera Solver v0.01c for Blender 2.8.x onwards
#     To be used with my A3DA script (or expect strange
#     results). This script bakes Diva cameras from their
#     native rig into the basic MMD rig. Now for the
#     obligatory FOV rant:
#
#     The field of view of a camera controls how much it sees.
#     This can be changed for artistic effect, and is done so
#     frequently in Diva games. But MMD has a large restriction
#     which prevents this from being usable - FOV values have
#     to be whole numbers, making smooth animations impossible.
#
#     This script offers two methods of exporting, both with
#     their own compromises:
#      - FOV bone animation. Exports the native vertical FOV
#        in degrees to be applied to a shader for perfect FOV.
#        One example is kh40's MES40 - I helped add a patch
#        for custom FOV, so all you need to do is apply the
#        VMD to the controller object. Unfortunately shaders
#        that support this are rare.
#      - FOV to distance estimation. Accurate FOV values are
#        used where possible, and a distance estimator fills
#        in the gaps to provide a similar effect. Less
#        accurate but produces a regular camera, which is
#        supported everywhere.
#
#     Both methods will use as many features as possible,
#     including automatic splitting based on camera cutting
#     to make your life easier.     
#
#     I recommend exporting both for compatibility sake. 


# ------------------------------------------------------------
#                         CREDITS
# ------------------------------------------------------------
# Script (old, don't judge)   - banitron (me, deviantArt)

# Feel free to edit. Please credit if you use this code.


# ------------------------------------------------------------
#                        HOW TO USE
# ------------------------------------------------------------
# Load your A3DA through my A3DA script for Blender. Make
# sure that an A3DA Camera exists somewhere in the scene.
# 
# After hitting run, find somewhere to save the file. You
# can choose to disable FOV to distance estimation which
# will drastically save time but won't produce shaderless
# cameras. You can also choose to disable dual 30fps and
# 60fps output but you won't gain much speed.
#
# Once output, the file with "MMD Camera" in it can just be
# used like any other camera.
# The files with "fov" are special, use those only if you
# have an FOV shader active. Any file with "_camera" at the
# end is only intended to be used on MMD's camera, not with
# your shader controller.
#
# This script uses Blender's settings to find the scene FPS
# and camera duration. My A3DA script, when importing just
# the camera, will set this automatically. Don't change
# these settings if you want this to work properly.
#
# Finally, I recommend opening the console while exporting
# your camera. If you're using MMD camera computation,
# Blender may appear to crash but the console will show the
# script is working as intended. My algorithm is quite
# heavy since it needs to trace the screen for each frame
# of the camera.


# ------------------------------------------------------------
#                 PLAY WITH THESE PARAMETERS!
# ------------------------------------------------------------
# Scales the position of camera. Default is 12.5
sf = 12.5


# Controls for how camera cut detection is found. Toy with
#     this if you're noticing weird camera cuts in FOV.

# Amount of per-axis movement before it becomes a cut.
movementThreshold = 0.075

# Minimum amount of keyframes between cuts.
#     Stops fast panning shots from being individual cuts
movementFrameThreshold = 8              


# Finally, controls for how FOV estimation is completed. Toy
#     with this if the FOV effect is not strong enough, or
#     you're experiencing weird clipping

# Absolute radius around target object to fit tracking points
camVectorSafetyArea = 0.25           

# Diameter on-screen around target to fit tracking points
camVectorViewingAreaRatio = 0.5

# Accuracy of view area fitting; high accuracy not required      
camVectorViewingAreaRegion = 0.01       





# ------------------------------------------------------------
#            SCRIPT BELOW - MODIFY WITH CAUTION
# ------------------------------------------------------------

camVectorSafetyRegion = 0.000001        # Accuracy of camera vectors; lower values produce less jitter at the cost of speed
camVectorFitViewingArea = True          # Dynamically adjust area around target. Reduces precision loss at the cost of speed
camRatio = 16/9                         # Ratio for all camera operations; assumed equal for import and export

defaultStepSize = 0.0125                # Step size of convergence algorithms; tweaking this can optimise the algorithm

import struct, math, bpy, mathutils
import bpy, bpy_extras, mathutils, math
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

def getDuplicateSafeName(name):
    if bpy.data.objects.find(name) != -1:
        dupIndex = 1
        while True:
            if bpy.data.objects.find(name + "_" + str(dupIndex)) == -1:
                return name + "_" + str(dupIndex)
            dupIndex += 1
    return name

def stringToFittedLength(inString, length):
    if len(inString) == length:
        return inString
    elif len(inString) < length:
        return (" " * (length - len(inString))) + inString
    else:
        return inString[0:length]

def smoothList(inList, tolerance):
    inList.sort()
    targetItem = None
    output = []
    for itemIndex in range(len(inList) - 1):
        if targetItem != None and (targetItem + tolerance > inList[itemIndex + 1]):
            targetItem = inList[itemIndex + 1]
        else:
            targetItem = inList[itemIndex]
            output.append(inList[itemIndex])
    return output

def hfovToVfov(fov):
    return 2 * math.atan(math.tan(fov / 2) * (1/camRatio))

def vfovToHfov(fov):
    return 2 * math.atan(math.tan(fov / 2) * camRatio)

def fovToFocalLength(camObject, fov):
    return camObject.data.sensor_width/2 / math.tan(fov/2)

def focalLengthToFov(camObject, focalLength):
    return 2 * math.atan((camObject.data.sensor_width/2) / focalLength)

def getCameraDirectionObject(cameraObj):
    for obj in cameraObj.parent.parent.parent.children:
        if obj.type == "EMPTY" and "Camera Direction" in obj.name:
            return obj
    return None

def findConstrainedCameras():
    # Find cameras created using A3DA Library
    output = []
    for obj in bpy.data.objects:
        try:
            if type(obj.data) == bpy.types.Camera:
                if "Camera Constraint" in obj.parent.name and "Camera Position" in obj.parent.parent.name and "MMD" not in obj.name:
                    output.append(obj)
        except:
            pass
    return output

def findCameraJumps(cameraObj):
    # Primitive - find camera jumps using movementThreshold against detected objects
    frameSplits = []
    for obj in cameraObj.parent.parent.parent.children:
        if obj.type == "EMPTY" and "Camera " in obj.name:
            if obj.animation_data != None:
                if obj.animation_data.action != None:
                    if len(obj.animation_data.action.fcurves) > 0:
                        print("Using " + obj.name)
                        for curve in obj.animation_data.action.fcurves:
                            if curve.data_path == "location":
                                lastFrameVal = 0
                                for frameIndex in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end):
                                    frameVal = curve.evaluate(frameIndex)
                                    if (frameVal - lastFrameVal) > movementThreshold:
                                        frameSplits.append(frameIndex)
                                    lastFrameVal = frameVal
    frameSplits.extend([bpy.context.scene.frame_start, bpy.context.scene.frame_end])
    return sorted(set(frameSplits))

def getOptimalTrackingPoints(cameraObj, trackObj, tempSafetyArea = None):
    # Dynamically optimise tracking points by matching a defined ratio
    if camVectorFitViewingArea:
        if tempSafetyArea == None:
            safetyArea = camVectorSafetyArea
        else:
            safetyArea = tempSafetyArea
        lastCycleType = None
        stepSize = defaultStepSize
        while abs(camVectorViewingAreaRatio - getCameraVectorLength(cameraObj, trackObj, safetyArea)[1]) > camVectorViewingAreaRegion:
            if camVectorViewingAreaRatio - getCameraVectorLength(cameraObj, trackObj, safetyArea)[1] > camVectorViewingAreaRegion:
                # Increase the distance of tracking points because the camera is currently too small
                if lastCycleType == "BACKWARD":     # Vector is attempting to converge
                    stepSize = stepSize / 2
                
                safetyArea += stepSize
                lastCycleType = "FORWARD"
            else:
                # Decrease the value of tracking points because the camera is currently too big
                if lastCycleType == "FORWARD":      # Vector is attempting to converge
                    stepSize = stepSize / 2
                
                safetyArea -= stepSize
                lastCycleType = "BACKWARD"
        return safetyArea
    return camVectorSafetyArea

def getCameraVectorLength(cameraObj, trackObj, safetyArea):
    # Measures a line across the viewing plane
    bpy.context.view_layer.update()
    pointOne = mathutils.Vector(trackObj.location)
    pointOne.z = pointOne.z + safetyArea
    pointTwo = mathutils.Vector(trackObj.location)
    pointTwo.z = pointTwo.z - safetyArea
    vecUp = bpy_extras.object_utils.world_to_camera_view(bpy.context.scene, cameraObj, pointOne)
    vecDown = bpy_extras.object_utils.world_to_camera_view(bpy.context.scene, cameraObj, pointTwo)
    vecLength = mathutils.Vector(mathutils.Vector(vecDown - vecUp)[0:2]).length
    if vecUp.z < 0 or vecDown.z < 0:
        return [False, vecLength]
    return [True, vecLength]

def addMmdCamera(cameraObj, cameraJumps):
    # Generates an MMD camera with constant FOV
    cameraJumps = smoothList(cameraJumps, movementFrameThreshold) + [cameraJumps[-1]]
    print("Detected cuts:\n" + str(cameraJumps) + "\n")
    
    bpy.ops.object.camera_add(location=(0,0,0), rotation=(0,0,0))
    mmdCam = bpy.context.object
    mmdCam.name = getDuplicateSafeName("MMD " + cameraObj.name)
    mmdCam.parent = cameraObj.parent
    mmdCam.animation_data_create()
    
    if cameraObj.animation_data != None and cameraObj.animation_data.action != None:
        mmdCam.animation_data.action = cameraObj.animation_data.action.copy()
    
    fovCurve = None
    if cameraObj.data.animation_data != None and cameraObj.data.animation_data.action != None:
        for curve in cameraObj.data.animation_data.action.fcurves:
            if curve.data_path == "lens":
                fovCurve = curve
                break
    
    if fovCurve != None:
        cameraDirectionObject = getCameraDirectionObject(cameraObj)
        stringLengthJump = len(str(len(cameraJumps) - 1))
        stringLengthFrame = len(str(bpy.context.scene.frame_end - bpy.context.scene.frame_start))
        for jumpPair in range(len(cameraJumps) - 1):
            focalLengthTotal = 0
            for focalIndex in range(cameraJumps[jumpPair], cameraJumps[jumpPair + 1]):
                focalLengthTotal += fovCurve.evaluate(focalIndex)
                
            tempFocalLength = focalLengthTotal / (cameraJumps[jumpPair + 1] - cameraJumps[jumpPair])
            tempWholeMmdFov = math.radians(round(math.degrees(hfovToVfov(focalLengthToFov(cameraObj, tempFocalLength)))))
            tempWholeMmdFov = vfovToHfov(tempWholeMmdFov)

            mmdCam.data.lens = fovToFocalLength(cameraObj, tempWholeMmdFov)
            mmdCam.data.keyframe_insert(data_path = "lens", frame = cameraJumps[jumpPair])
            mmdCam.data.keyframe_insert(data_path = "lens", frame = cameraJumps[jumpPair + 1] - 1)

            hopsInCycle = 0
            lastSafetyArea = None
            for frameIndex in range(cameraJumps[jumpPair], cameraJumps[jumpPair + 1]):
                bpy.context.scene.frame_set(frameIndex)
                
                # Use the stationary tracking points to verify base tracking conditions
                outVecLength = getCameraVectorLength(mmdCam, cameraDirectionObject, camVectorSafetyArea)
                
                if not(outVecLength[0]):                    # Camera is facing backwards to target
                    bpy.context.object.location[2] = 0      #     so reset its position

                safetyArea = getOptimalTrackingPoints(cameraObj, cameraDirectionObject, tempSafetyArea = lastSafetyArea)
                inVecLength = getCameraVectorLength(cameraObj, cameraDirectionObject, safetyArea)[1]
                outVecLength = getCameraVectorLength(mmdCam, cameraDirectionObject, safetyArea)[1]
                
                lastOutVecLength = 0
                lastSafetyArea = safetyArea
                lastCycleType = None
                
                noProgressionCounter = 0
                stepSize = defaultStepSize
                
                while True:
                    if abs(outVecLength - inVecLength) <= camVectorSafetyRegion:
                        # View area has reached safety region
                        lastCycleType = None
                        stepSize = defaultStepSize
                        break
                    
                    elif outVecLength < inVecLength:
                        # View area is smaller then it should be, camera needs to be panned back (z-)
                        if lastCycleType != "BACKWARD":
                            stepSize = stepSize / 2
                        lastCycleType = "BACKWARD"
                        
                        bpy.context.object.location[2] -= stepSize
                        outVecLength = getCameraVectorLength(mmdCam, cameraDirectionObject, safetyArea)[1]
                        hopsInCycle += 1
 
                    else:
                        # View area is bigger than it should be, camera needs to be panned forward (z+)
                        if lastCycleType != "FORWARD":
                            stepSize = stepSize / 2
                        lastCycleType = "FORWARD"
    
                        bpy.context.object.location[2] += stepSize
                        outVecLength = getCameraVectorLength(mmdCam, cameraDirectionObject, safetyArea)[1]
                        hopsInCycle += 1
                    
                    if outVecLength == lastOutVecLength:
                        noProgressionCounter += 1
                    if noProgressionCounter > 5:            # Break if the algorithm is stuck (bad step size)
                        break

                    lastOutVecLength = outVecLength

                mmdCam.keyframe_insert(data_path = "location", index=2, frame = frameIndex)
            
            print(stringToFittedLength(str(jumpPair + 1), stringLengthJump) + "/" + stringToFittedLength(str(len(cameraJumps) - 1), stringLengthJump) + ": " + stringToFittedLength(str(noProgressionCounter), 1) + " failures\t " + stringToFittedLength(str(cameraJumps[jumpPair + 1] - cameraJumps[jumpPair]), stringLengthFrame) + " frames, " + str(hopsInCycle) + " hops")
    return mmdCam

# VMD library starts here
# Gutted and rotted version of VMD library that only supports bones and cameras

def stringToJpnLength(text, length):
    text = text.encode('shift-jis')
    if len(text) > length:
        text = text[0:20]
    elif len(text) < length:
        text = bytearray(text)
        for x in range(length - len(text)): text.extend(b'\x00')
    return text

class Vec3(object):
    def __init__(self,x,y,z):
        self.x = x
        self.y = y
        self.z = z
    def __add__(self,q2):
        return Vec3(self.x + q2.x, self.y + q2.y, self.z + q2.z)
    def normalise(self):
        magnitude = math.sqrt((self.x * self.x) + (self.y * self.y) + (self.z * self.z))
        return Vec3(self.x / magnitude, self.y / magnitude, self.z / magnitude)

class Vec4(Vec3):
    def __init__(self,x,y,z,w):
        Vec3.__init__(self,x,y,z)
        self.w = w
    def toMmdEuler(self):
        test = abs(self.x * self.y + self.z * self.w)
        if test >= 0.5 or test <= -0.5:
            z = 0
            if test >= 0.5:
                x = 2 * math.atan2(self.x, self.w)
                y = math.pi / 2
            else:
                x = -2 * math.atan2(self.x, self.w)
                y = - math.pi / 2
        else:
            sqx = self.x * self.x
            sqy = self.y * self.y
            sqz = self.z * self.z
            x = math.atan2(2 * self.y * self.w - 2 * self.x * self.z, 1 - 2 * sqy - 2 * sqz)
            y = math.asin(2 * test)
            z = math.atan2(2 * self.x * self.w - 2 * self.y * self.z, 1 - 2 * sqx - 2 * sqz)
        return Vec3(z, x, -y)
    def __mul__(self,q2):
        return Vec4(-q2.x * self.x -    q2.y * self.y -     q2.z * self.z +     q2.w * self.w,
                    q2.x * self.w +     q2.y * self.z -     q2.z * self.y +     q2.w * self.x,
                    -q2.x * self.z +    q2.y * self.w +     q2.z * self.x +     q2.w * self.y,
                    q2.x * self.y -     q2.y * self.x +     q2.z * self.w +     q2.w * self.z)

class Keyframe(object):
    def __init__(self):
        self.name = ""
        self.index = 0

class KeyframeBone(Keyframe):
    def __init__(self):
        Keyframe.__init__(self)
        self.pos = None
        self.rot = None

class KeyframeCamera(Keyframe):
    def __init__(self):
        Keyframe.__init__(self)
        self.distance = 45
        self.pos = None
        self.rot = None
        self.fov = 30
        self.pers = True
        
class AnimationVmd(object):
    def __init__(self):
        self.name = ""
        self.keyframeBones = []
        self.keyframeCamera = []
    
    def export(self, filename, cameraCuts, camExtension = " - Camera.vmd"):
        
        def getClosestCut(value):
            targetVal = value + 10000
            lastVal = None
            for val in cameraCuts:
                if val > targetVal:
                    break
                else:
                    lastVal = val
                    if val == cameraCuts[-1]:
                        break
                    
            if lastVal == None or lastVal <= value:
                lastVal = targetVal
            return lastVal
        
        if self.keyframeCamera != []:
            print("Exporting camera...")
            if len(self.keyframeCamera) > 10000:
                print("Warning - camera will have to be split up!")
                currentFrame = 0
                while currentFrame != cameraCuts[-1]:
                    nextFrame = getClosestCut(currentFrame)
                    self.binaryExporter(filename + " - " + str(currentFrame) + " to " + str(nextFrame - 1) + camExtension, b'\x83\x4A\x83\x81\x83\x89\x81\x45\x8F\xC6\x96\xBE\x00on Data', [], self.keyframeCamera[currentFrame:nextFrame])
                    currentFrame = nextFrame
            else:
                self.binaryExporter(filename + camExtension, b'\x83\x4A\x83\x81\x83\x89\x81\x45\x8F\xC6\x96\xBE\x00on Data', [], self.keyframeCamera)

        if self.keyframeBones != []:
            print("Exporting motion...")
            encodedName = stringToJpnLength(self.name, 20)
            self.binaryExporter(filename + ".vmd", encodedName, self.keyframeBones,[])

    def binaryExporter(self, filename, encodedModelName, keyframeBones, keyframeCamera):
        with open(filename, 'wb') as output:
            output.write(b'Vocaloid Motion Data 0002\x00\x00\x00\x00\x00' + encodedModelName +
                         len(keyframeBones).to_bytes(4, byteorder = 'little'))
            for frame in keyframeBones:
                output.write(stringToJpnLength(frame.name, 15) + frame.index.to_bytes(4, byteorder = 'little'))
                output.write(struct.pack("<f", frame.pos.x) + struct.pack("<f", frame.pos.y) +
                             struct.pack("<f", frame.pos.z) + struct.pack("<f", frame.rot.x) +
                             struct.pack("<f", frame.rot.y) + struct.pack("<f", frame.rot.z) +
                             struct.pack("<f", frame.rot.w))
                output.write(b'\x14\x14\x14\x14\x14\x14\x14\x14kkkkkkkk\x14\x14\x14\x14\x14\x14\x14kkkkkkkk\x01\x14\x14\x14\x14\x14\x14kkkkkkkk\x01\x00\x14\x14\x14\x14\x14kkkkkkkk\x01\x00\x00')
            
            output.write(b'\x00\x00\x00\x00')
            output.write(len(keyframeCamera).to_bytes(4, byteorder = 'little'))
            for frame in keyframeCamera:
                output.write(frame.index.to_bytes(4, byteorder = 'little') + struct.pack("<f", - frame.distance) +
                             struct.pack("<f", frame.pos.x) + struct.pack("<f", frame.pos.y) +
                             struct.pack("<f", frame.pos.z) + struct.pack("<f", frame.rot.x) +
                             struct.pack("<f", frame.rot.y) + struct.pack("<f", frame.rot.z))
                output.write(b'\x14\x6B\x14\x6B\x14\x6B\x14\x6B\x14\x6B\x14\x6B\x14\x6B\x14\x6B\x14\x6B\x14\x6B\x14\x6B\x14\x6B')
                output.write((int(frame.fov)).to_bytes(4, byteorder = 'little'))
                if frame.pers == True:
                    output.write(b'\x00')
                else:
                    output.write(b'\x01')
            
            output.write(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
                
        print("Finished.")

    def sortFrames(self):
        self.keyframeBones.sort(key=lambda x: x.index, reverse=False)
        self.keyframeCamera.sort(key=lambda x: x.index, reverse=False)


def focalLengthToFov(camObject, focalLength):
    return 2 * math.atan((camObject.data.sensor_width/2) / focalLength)

def hfovToVfov(fov):
    return 2 * math.atan(math.tan(fov / 2) * (1/camRatio))

def blenderDataToMmdData(cameraObj):
    # This requires the scene to be updated as it accesses the object matrix - credit to mmd_tools
    mmdRotMatrix = mathutils.Matrix(([1,0,0,0], [0,0,1,0], [0,-1,0,0], [0,0,0,1]))
    mmdRotationXyz = (cameraObj.matrix_world @ mmdRotMatrix).to_euler('YXZ')
    return cameraObj.matrix_world.translation, mmdRotationXyz

def exportCamera(cameraObj):
    output = []
    focalLength = None
    if cameraObj.data.animation_data != None and cameraObj.data.animation_data.action != None:
        for animTrack in cameraObj.data.animation_data.action.fcurves:
            if animTrack.data_path == "lens":
                focalLength = animTrack
                break
    
    for frameIndex in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end):
        bpy.context.scene.frame_set(frameIndex)
        mmdData = blenderDataToMmdData(cameraObj)
        if focalLength != None:
            focalDeg = math.degrees(hfovToVfov(focalLengthToFov(cameraObj, focalLength.evaluate(frameIndex))))
        else:
            focalDeg = 30
        output.append([frameIndex, mmdData[0].x, mmdData[0].y, mmdData[0].z, mmdData[1].x, mmdData[1].y, mmdData[1].z, focalDeg])
    
    return output

def transformBlenderDump(vmdObject, blenderDump):
    for frameData in blenderDump:
        tempKeyframeCamera = KeyframeCamera()
        tempKeyframeCamera.index = int(frameData[0])
        tempKeyframeCamera.distance = 0
        tempKeyframeCamera.pos = Vec3(float(frameData[1]) * sf, float(frameData[3]) * sf, float(frameData[2]) * sf)
        tempKeyframeCamera.rot = Vec3(float(frameData[4]), float(frameData[6]), float(frameData[5]))
        tempKeyframeCamera.fov = float(frameData[7])
        vmdObject.keyframeCamera.append(tempKeyframeCamera)

def halveFrameRate(vmdObject):
    snappedFrames = []
    for frame in vmdObject.keyframeCamera:
        if frame.index % 2 == 0:
            frame.index = frame.index // 2
            snappedFrames.append(frame)
    vmdObject.keyframeCamera = snappedFrames

def createFovBone(vmdObject):
    for frame in vmdObject.keyframeCamera:
        tempFrame = KeyframeBone()
        tempFrame.name = "fov"
        tempFrame.index = frame.index
        tempFrame.pos = Vec3(frame.fov, 0, 0)
        tempFrame.rot = Vec4(0,0,0,0)
        frame.fov = 30
        vmdObject.keyframeBones.append(tempFrame)


def exportData(filename, computeMmdCamera, addHalfFrameRate):
    
    def generateNewVmd(data):
        outputVmd = AnimationVmd()
        transformBlenderDump(outputVmd, data)
        return outputVmd
    
    def getHalvedCamJump(jumps):
        tempJumps = list(jumps)
        output = []
        for value in tempJumps:
            value = value // 2
            if value not in output:
                output.append(value)
        return output
    
    if filename[-4:] == ".vmd":
        baseFilename = filename[:-4]
    else:
        baseFilename = filename
    
    sceneCameras = findConstrainedCameras()
    mmdCameras = []
    jumpCameras = []
    
    fps = bpy.context.scene.render.fps * bpy.context.scene.render.fps_base
    if round(fps) == fps:
        fps = round(fps)
    else:
        fps = math.ceil(fps)

    # TODO - Length of anim from camera, not from scene. Multi camera support almost there
    for indexCamera, camera in enumerate(sceneCameras):
        jumpCameras.append(findCameraJumps(camera))
        if computeMmdCamera:
            mmdCameras.append(addMmdCamera(camera, jumpCameras[-1]))
    
    for indexCamera, camera in enumerate(sceneCameras):
        # TODO - Name, LUL
        camData = exportCamera(camera)
        outputVmd = generateNewVmd(camData)
        createFovBone(outputVmd)
        outputVmd.export(baseFilename + " FOV " + camera.name + ", " + str(fps) + "fps", jumpCameras[indexCamera])
        
        if addHalfFrameRate:
            outputVmd = generateNewVmd(camData)
            halveFrameRate(outputVmd)
            createFovBone(outputVmd)
            outputVmd.export(baseFilename + " FOV " + camera.name + ", " + str(fps // 2) + "fps", getHalvedCamJump(jumpCameras[indexCamera]))
    
    for indexCamera, camera in enumerate(mmdCameras):
        # TODO - Name, LUL
        camData = exportCamera(camera)
        outputVmd = generateNewVmd(camData)
        outputVmd.export(baseFilename + " " + camera.name + ", " + str(fps) + "fps", jumpCameras[indexCamera])
        
        if addHalfFrameRate:
            outputVmd = generateNewVmd(camData)
            halveFrameRate(outputVmd)
            outputVmd.export(baseFilename + " " + camera.name + ", " + str(fps // 2) + "fps", getHalvedCamJump(jumpCameras[indexCamera]))
    

class ExportSomeData(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "export_test.some_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export A3DA Camera"

    # ExportHelper mixin class uses this
    filename_ext = ".vmd"

    filter_glob: StringProperty(
        default="*.vmd",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    generateMmdCam: BoolProperty(
        name="Compute safe MMD camera",
        description="Compute a new camera which uses distance for FOV. Captures most of the effect\nbut is compatible with every shader. Uncheck if you are certain your shader\nis compatible with this script or have a slower computer",
        default=True,
    )

    generateHalfFrameRate: BoolProperty(
        name="Generate half frame rate versions",
        description="Output 30fps cameras with the 60fps native output",
        default=True,
    )

    def execute(self, context):
        exportData(self.filepath, self.generateMmdCam, self.generateHalfFrameRate)
        unregister()
        return {'FINISHED'}

def register():
    bpy.utils.register_class(ExportSomeData)

def unregister():
    bpy.utils.unregister_class(ExportSomeData)

register()
bpy.ops.export_test.some_data('INVOKE_DEFAULT')