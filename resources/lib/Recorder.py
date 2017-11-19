#!/usr/bin/python
# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
import xbmcgui
import sys
import urllib
import re
import subprocess

from .helpers import *

class RecSettings:
    
    @staticmethod
    def defaultRecordQuality(qualityList):
	recordQuality = xbmcaddon.Addon().getSetting("recordQuality")
	try:
	    return qualityList[int(recordQuality)]
	except (IndexError, ValueError):
            return qualityList[2 if len(qualityList) > 2 else 0]


def transl(translationId):
    return xbmcaddon.Addon().getLocalizedString(translationId).encode("utf-8")

def recLog(message, level=xbmc.LOGNOTICE):
    output = "[ORF TVTHEK] (Recorder): " + message
    xbmc.log(msg=output, level=level)

def recGetPluginMode():
    return "recordStream"

def recContextMenuItem(pluginHandle, title, videourl, plot, date, duration, channel, banner):
    recParams = {"mode" : recGetPluginMode(),
                 "title": title, "videourl": videourl,
                 "plot": plot, "aired": date,
                 "duration": duration, "channel": channel,
                 "banner": banner}
    recPluginURL = sys.argv[0] + "?" + urllib.urlencode(recParams)
    return (transl(30903).encode("utf-8"), "XBMC.RunPlugin(%s)" % recPluginURL)

def recExtractManifestURL(videourl):
    # Remove plugin://...videourl=
    ret = re.sub(r".*videourl%3Dhttp", "http", videourl)
    # Replace %xx escapes and plus signs with their single-char equivalent
    ret = urllib.unquote_plus(ret)
    # Change delivery method progressive to hds
    ret = re.sub(r"/online/[0-9a-f]+/[0-9a-fA-F]+/", "/", ret)
    ret = ret.replace("apasfpd.apa.at/", "apasfiis.apa.at/f4m/") + "/manifest.f4m"
    return ret

def recVideourlChangeQuality(videourl, new_qualityString):
    newQS = "_" + new_qualityString
    return (videourl.replace("_q8c", newQS).replace("_Q8C", newQS)
                    .replace("_q6a", newQS).replace("_Q6A", newQS)
                    .replace("_q4a", newQS).replace("_Q4A", newQS)
                    .replace("_q1a", newQS).replace("_Q1A", newQS))

def recGenerateNFO(title, plot, aired, duration, channel, genre, tags):
    #TODO
    recLog("TODO: recGenerateNFO")

def recRecord(title, videourl, plot, aired, duration, channel, banner, videoQualityStrings):
    title = urllib.unquote_plus(title)
    plot = urllib.unquote_plus(plot)
    channel = urllib.unquote_plus(channel)

    params = recShowParamDialogs()
    quality = videoQualityStrings[params[0]]
    targetFolder = params[1]
    useSeparateFolder = params[2]
    genre = params[3]
    tagString = params[4]

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

    recGenerateNFO(title, plot, aired, duration, channel, genre, tagString)
    
    recCommand = "php AdobeHDS.php --manifest \"%s\" --delete --outdir \"%s\" --outfile \"%s\"" % (manifestURL, targetFolder, targetFile)

    recLog(title + "[" + recCommand + "]: " + channel + ", " + duration + ", " + banner)

    #try:
    #    subprocess.Popen(args=recCommand)
    #except:
    #    logSome("The specified record command yielded an error!", xbmc.LOGERROR)


def recShowParamDialogs():
    dialog = xbmcgui.Dialog()
    defaultQuality = RecSettings.defaultRecordQuality(range(4))
    quality = dialog.select(transl(30904),
                            [transl(i) for i in [30023, 30024, 30025, 30044]],
                            preselect=defaultQuality)

    #TODO default folder as setting
    folder = dialog.browseSingle(3, transl(30905), "video")

    useSeparateFolder = dialog.yesno(transl(30906), transl(30907))

    #TODO default genre as setting
    genre = dialog.input(transl(30909))

    #TODO default tags as setting
    tags = dialog.input(transl(30910))
    
    return [quality, folder, useSeparateFolder, genre, tags]

def recShowProgressDialog():
    pDialog = xbmcgui.DialogProgress()
    #someLog("Title: %s" % title.encode('UTF-8'),'Info')
    #someLog("Videourl: %s" % urllib.unquote(videourl),'Info')
    #pDialog.create("ORF TVthek", urllib.unquote(title).encode('UTF-8'), "", "Recording stream...")
    #pDialog.update( 2, urllib.unquote(title).encode('UTF-8'), "", "Recording stream...")
    #time.sleep(2)
    #pDialog.update(50, urllib.unquote(title).encode('UTF-8'), "", "Saving video file...")
    #time.sleep(2)
    #pDialog.update(75, urllib.unquote(title).encode('UTF-8'), "", "Saving nfo file...")
    #time.sleep(2)
    #pDialog.close()
