#!/usr/bin/python
# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
import xbmcgui
import sys
import urllib
import re
import subprocess
import os
import select

from .helpers import *

class RecSettings:
    """Helper class with static methods for retrieving settings values."""
    _addon = xbmcaddon.Addon()
    @staticmethod
    def defaultRecordQuality(qualityList):
	recordQuality = RecSettings._addon.getSetting("recordQuality")
	try:
	    return qualityList[int(recordQuality)]
	except (IndexError, ValueError):
            return qualityList[2 if len(qualityList) > 2 else 0]
    @staticmethod
    def defaultFolder():
        return RecSettings._addon.getSetting("recordFolder")
    @staticmethod
    def defaultGenre():
        return RecSettings._addon.getSetting("recordGenre")
    @staticmethod
    def defaultTagString():
        return RecSettings._addon.getSetting("recordTags")
    @staticmethod
    def defaultTags():
        return RecSettings._addon.getSetting("recordTags").split(",")


def transl(translationId):
    """Returns the translated string with the given id."""
    return xbmcaddon.Addon().getLocalizedString(translationId).encode("utf-8")


def recLog(message, level=xbmc.LOGNOTICE):
    """Log a message."""
    output = "[ORF TVTHEK] (Recorder): " + message
    xbmc.log(msg=output, level=level)


def recGetPluginMode():
    """Returns the plugin mode string."""
    return "recordStream"


def recContextMenuItem(pluginHandle, title, videourl, plot, date, duration, channel, banner):
    """Create a contextMenuItem (i.e. a tuple(label, action))
       to be used for stream recording action.
    """
    recParams = {"mode" : recGetPluginMode(),
                 "title": title, "videourl": videourl,
                 "plot": plot, "aired": date,
                 "duration": duration, "channel": channel,
                 "banner": banner}
    recPluginURL = sys.argv[0] + "?" + urllib.urlencode(recParams)
    return (transl(30903).encode("utf-8"), "XBMC.RunPlugin(%s)" % recPluginURL)


def recExtractManifestURL(videourl):
    """Create the manifest URL out of a given videourl."""
    # Remove plugin://...videourl=
    ret = re.sub(r".*videourl%3Dhttp", "http", videourl)
    # Replace %xx escapes and plus signs with their single-char equivalent
    ret = urllib.unquote_plus(ret)
    # Change delivery method progressive to hds
    ret = re.sub(r"/online/[0-9a-f]+/[0-9a-fA-F]+/", "/", ret)
    ret = ret.replace("apasfpd.apa.at/", "apasfiis.apa.at/f4m/") + "/manifest.f4m"
    return ret


def recVideourlChangeQuality(videourl, new_qualityString):
    """Replace the quality string in a given videourl with the given new one."""
    newQS = "_" + new_qualityString
    return (videourl.replace("_q8c", newQS).replace("_Q8C", newQS)
                    .replace("_q6a", newQS).replace("_Q6A", newQS)
                    .replace("_q4a", newQS).replace("_Q4A", newQS)
                    .replace("_q1a", newQS).replace("_Q1A", newQS))


def recRecord(title, videourl, plot, aired, duration, channel, banner, videoQualityStrings):
    """Do the stream record."""
    title = urllib.unquote_plus(title).encode('UTF-8')
    plot = urllib.unquote_plus(plot).encode('UTF-8')
    channel = urllib.unquote_plus(channel)

    (quality, targetFolder, useSeparateFolder, genre, tagString) = recShowParamDialogs()
    quality = videoQualityStrings[quality]

    if not targetFolder:
        notifyUser(transl(30908))
        return
    
    manifestURL = recExtractManifestURL(videourl)
    manifestURL = recVideourlChangeQuality(manifestURL, quality)

    if not aired:  #try to get aired date from manifestURL
        found = manifestURL.find("worldwide")
        if found > -1:
            tmpAired = manifestURL[(found+10):(found+20)]
            if None != re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", tmpAired):
                aired = tmpAired
    
    targetFile = (aired + "_" + title.replace(":","_")
                  .replace(" ","-").replace("?","").replace("!",""))
    if useSeparateFolder:
        targetFolder = targetFolder + targetFile + "/"
    targetFile = targetFile + ".flv"

    pDialog = xbmcgui.DialogProgress()
    pDialog.create("ORF-TVthek Recorder", title, "", transl(30914))
    if recDownloadStream(manifestURL, targetFolder, targetFile, pDialog, title):
        recGenerateNFO(title, plot, aired, duration, channel, genre, tagString, pDialog, title)
        notifyUser(title + "\n" + transl(30917), 3000)  #done
    else:
        notifyUser(title + "\n" + transl(30918), 3000)  #error
    pDialog.close()


def recShowParamDialogs():
    """Show dialogs questioning download/storing parameters."""
    dialog = xbmcgui.Dialog()
    defaultQuality = RecSettings.defaultRecordQuality(range(4))
    quality = dialog.select(transl(30904),
                            [transl(i) for i in [30023, 30024, 30025, 30044]],
                            preselect=defaultQuality)

    folder = dialog.browseSingle(3, transl(30905), "video", defaultt=RecSettings.defaultFolder())

    useSeparateFolder = dialog.yesno(transl(30906), transl(30907))

    genre = dialog.input(transl(30909), defaultt=RecSettings.defaultGenre())

    tags = dialog.input(transl(30910), defaultt=RecSettings.defaultTagString())
    
    return (quality, folder, useSeparateFolder, genre, tags)


def recGenerateNFO(title, plot, aired, duration, channel, genre, tags, pDialog=None, pDialogHeading=""):
    """Generate an NFO file for the given properties."""
    #TODO
    #pDialog.update(int(percentage), pDialogHeading, "", transl(30916))
    recLog("TODO: recGenerateNFO")


def recDownloadStream(manifestURL, targetFolder, targetFile, pDialog=None, pDialogHeading=""):
    """Actually download the stream."""
    binPath = xbmcaddon.Addon().getAddonInfo('path') + "/resources/lib/stream-recorder/"
    recCommand = "php AdobeHDS.php --manifest %s --outdir %s --outfile %s --delete" % (manifestURL, targetFolder, targetFile)

    recLog("binPath: " + binPath)
    recLog("recCommand: " + recCommand)
    try:
        proc = subprocess.Popen(args=recCommand.split(" "),
                                cwd=binPath, stdout=subprocess.PIPE)
        if pDialog:
            running = True #TODO error handling!!!
            noOfFragments = None
            while running:
                rlist, wlist, xlist = select.select([proc.stdout], [], [])
                for stdout in rlist:
                    txt = os.read(stdout.fileno(), 1024)
                    fragm = re.search(r"Downloading ([0-9]+)/([0-9]+) fragments", txt)
                    if fragm:
                        percentage = int(fragm.group(1)) * 100.0 / int(fragm.group(2))
                        pDialog.update(int(percentage), pDialogHeading, "", transl(30915))
                    running = (txt.find("Finished") == -1)
        outs, errs = proc.communicate()
        recLog("outs, errs: " + str(outs) + " ;; " + str(errs))
        return proc.returncode == 0
    except:
        recLog("The record command yielded an error!", xbmc.LOGERROR)
        return False
