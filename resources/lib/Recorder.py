#!/usr/bin/python
# -*- coding: utf-8 -*-

import xbmc, xbmcaddon, xbmcgui
import urllib, re
import sys, os, os.path
import subprocess, select
import datetime

from .helpers import *

class RecSettings:
    """Helper class with static methods for retrieving settings values."""
    _addon = xbmcaddon.Addon()
    @staticmethod
    def askRecordQuality():
        return RecSettings._addon.getSetting("askRecordQuality") == "true"
    @staticmethod
    def defaultRecordQuality(qualityList):
        recordQuality = RecSettings._addon.getSetting("recordQuality")
        try:
            return qualityList[int(recordQuality)]
        except (IndexError, ValueError):
            return qualityList[2 if len(qualityList) > 2 else 0]
    @staticmethod
    def askFolder():
        return RecSettings._addon.getSetting("askRecordFolder") == "true"
    @staticmethod
    def defaultFolder():
        return RecSettings._addon.getSetting("recordFolder")
    @staticmethod
    def askUseSeparateFolder():
        return RecSettings._addon.getSetting("askUseSeparateFolder") == "true"
    @staticmethod
    def defaultUseSeparateFolder():
        return RecSettings._addon.getSetting("useSeparateFolder") == "true"
    @staticmethod
    def askFilename():
        return RecSettings._addon.getSetting("askRecordFilename") == "true"
    @staticmethod
    def askSaveNFO():
        return RecSettings._addon.getSetting("askSaveNFO") == "true"
    @staticmethod
    def defaultSaveNFO():
        return RecSettings._addon.getSetting("saveNFO") == "true"
    @staticmethod
    def askSaveThumb():
        return RecSettings._addon.getSetting("askSaveThumb") == "true"
    @staticmethod
    def defaultSaveThumb():
        return RecSettings._addon.getSetting("saveThumb") == "true"
    @staticmethod
    def askMediaType():
        return RecSettings._addon.getSetting("askRecordMediaType") == "true"
    @staticmethod
    def defaultMediaType(mediaTypeList):
        mediaType = RecSettings._addon.getSetting("recordMediaType")
        try:
            return mediaTypeList[int(mediaType)]
        except (IndexError, ValueError):
            return mediaTypeList[0]
    @staticmethod
    def askGenre():
        return RecSettings._addon.getSetting("askRecordGenre") == "true"
    @staticmethod
    def defaultGenre():
        return RecSettings._addon.getSetting("recordGenre")
    @staticmethod
    def askTagString():
        return RecSettings._addon.getSetting("askRecordTags") == "true"
    @staticmethod
    def defaultTagString():
        return RecSettings._addon.getSetting("recordTags")
    @staticmethod
    def defaultTags():
        return RecSettings._addon.getSetting("recordTags").split(",")
    @staticmethod
    def defaultTvShow():
        return RecSettings._addon.getSetting("recordTvShow")


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


def myNotify(message, header=None, time_=3000, icon=None):
    """Send notification. If header==None the addon-name is used.
       If icon==None the addon-icon is used.
    """
    _addon = xbmcaddon.Addon()
    header = _addon.getAddonInfo('name') if not header else header
    icon   = _addon.getAddonInfo('icon') if not icon else icon
    xbmcgui.Dialog().notification(header, message, icon, time_)

def myNotifyError(message, header=None, time_=3000):
    myNotify(message, header, time_, xbmcgui.NOTIFICATION_ERROR)

def myNotifyWarning(message, header=None, time_=3000):
    myNotify(message, header, time_, xbmcgui.NOTIFICATION_WARNING)

def myNotifyInfo(message, header=None, time_=3000):
    myNotify(message, header, time_, xbmcgui.NOTIFICATION_INFO)


def recContextMenuItem(pluginHandle, title, videourl, plot, date,
                       duration, channel, banner):
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
    ret = ret.replace("apasfpd.apa.at/", "apasfiis.apa.at/f4m/"
                      ) + "/manifest.f4m"
    return ret


def recVideourlChangeQuality(videourl, new_qualityString):
    """Replace the quality string in a given videourl with the given new one."""
    newQS = "_" + new_qualityString
    return (videourl.replace("_q8c", newQS).replace("_Q8C", newQS)
                    .replace("_q6a", newQS).replace("_Q6A", newQS)
                    .replace("_q4a", newQS).replace("_Q4A", newQS)
                    .replace("_q1a", newQS).replace("_Q1A", newQS))


def recRecord(title, videourl, plot, aired, duration, channel,
              thumb, videoQualityStrings):
    """Do the stream record."""
    title = urllib.unquote_plus(title).encode('UTF-8')
    plot = urllib.unquote_plus(plot).encode('UTF-8')
    channel = urllib.unquote_plus(channel)
    thumb = urllib.unquote_plus(thumb)

    (quality, targetFolder, useSeparateFolder, saveNFO, saveThumb,
     mediaType, tvshow, genre, tagString) = recShowParamDialogs()

    if not targetFolder:  #user did not choose a folder -> cancel
        myNotify(transl(30908))
        return

    quality = videoQualityStrings[quality]
    if saveNFO and mediaType is not None:
        mediaType = ["movie", "episodedetails"][mediaType]

    #get URL of manifest file
    manifestURL = recExtractManifestURL(videourl)
    manifestURL = recVideourlChangeQuality(manifestURL, quality)

    #try to get aired date from manifestURL
    if not aired:
        found = manifestURL.find("worldwide")
        if found > -1:
            tmpAired = manifestURL[(found+10):(found+20)]
            if None != re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", tmpAired):
                aired = tmpAired
    # otherwise take current date
    if not aired:
        aired = datetime.datetime.now().strftime("%Y-%m-%d")

    # build (default) filename
    targetFile = (aired + "_" + title.replace(":","_")
                  .replace(" ","-").replace("?","").replace("!","")
                  .replace("/","").replace("\\",""))

    # ask user for filename
    if RecSettings.askFilename():
        targetFile = xbmcgui.Dialog().input(transl(30934), defaultt=targetFile)
        targetFile = (targetFile.replace("?","").replace("!","")
                      .replace("/","").replace("\\",""))

    if useSeparateFolder:
        targetFolder = targetFolder + targetFile + "/"
    targetFile = targetFile + ".flv"

    if os.path.isfile(targetFolder  + "/" + targetFile):
        if not xbmcgui.Dialog().yesno(transl(30906), transl(30935)):
            #TODO if overwrite? == No => ask for new filename
            myNotify(transl(30908))
            return

    #create folder structure
    try: os.makedirs(targetFolder)
    except: pass

    # show progress while downloading and saving
    pDialog = xbmcgui.DialogProgress()
    pDialog.create(transl(30906), title, "", transl(30914))
    
    if recDownloadStream(manifestURL, targetFolder, targetFile, pDialog, title):
        if saveNFO:
            nfoFile = targetFolder + targetFile[:-4] + ".nfo"
            recGenerateNFO(nfoFile, title, plot, aired, duration, channel,
                           mediaType, tvshow, genre, tagString, pDialog, title)
        if saveThumb and thumb:
            thumbFile = targetFolder + targetFile[:-4] + "-thumb.jpg"
            recDownloadThumb(thumbFile, thumb)
        myNotify(cutStr(title, 25) + "\n" + transl(30917))  #done
    else:
        myNotifyError(cutStr(title, 25) + "\n" + transl(30918))  #error
    pDialog.close()


def recShowParamDialogs():
    """Show dialogs questioning download/storing parameters."""
    dialog = xbmcgui.Dialog()

    #ask: quality
    defaultQuality = RecSettings.defaultRecordQuality(range(4))
    quality = defaultQuality if not RecSettings.askRecordQuality() else \
              dialog.select(transl(30904),
                            [transl(i) for i in [30023, 30024, 30025, 30044]],
                            preselect=defaultQuality)

    #ask: folder
    folder = RecSettings.defaultFolder() if not RecSettings.askFolder() else \
             dialog.browseSingle(3, transl(30905), "video",
                                 defaultt=RecSettings.defaultFolder())

    useSeparateFolder = RecSettings.defaultUseSeparateFolder() if not \
                                RecSettings.askUseSeparateFolder() else \
                        dialog.yesno(transl(30906), transl(30907))

    #ask: save a NFO file?
    saveNFO = RecSettings.defaultSaveNFO() if not RecSettings.askSaveNFO() else \
              dialog.yesno(transl(30906), transl(30933))

    #ask: save a thumbnail image?
    saveThumb = RecSettings.defaultSaveThumb() if not RecSettings.askSaveThumb() else \
                dialog.yesno(transl(30906), transl(30939))

    mediaType = None
    tvshow = None
    genre = None
    tags = None
    if saveNFO:
        #ask: media type (movie/episode)
        defaultMediaType = RecSettings.defaultMediaType(range(2))
        mediaType = defaultMediaType if not RecSettings.askMediaType() else \
                  dialog.select(transl(30932), [transl(i) for i in [30924, 30925]],
                                preselect=defaultMediaType)

        #ask: TV-show (if episode)
        if mediaType == 1:
            tvshow = dialog.input(transl(30936),
                                  defaultt=RecSettings.defaultTvShow())

        #ask: genre
        genre = RecSettings.defaultGenre() if not RecSettings.askGenre() else \
                dialog.input(transl(30909), defaultt=RecSettings.defaultGenre())

        #ask: tags
        tags = RecSettings.defaultTagString() if not RecSettings.askTagString() else \
                dialog.input(transl(30910), defaultt=RecSettings.defaultTagString())
    
    return (quality, folder, useSeparateFolder, saveNFO, saveThumb,
            mediaType, tvshow, genre, tags)

def recGenerateNFO(filepath, title, plot, aired, duration, channel, mediaType,
                   tvShowName, genres, tags, pDialog=None, pDialogHeading=""):
    """Generate an NFO file for the given properties."""

    def _progress(percentage):
        if pDialog:
            pDialog.update(percentage, pDialogHeading, "", transl(30916))

    _progress(2)
    try:
        f = open(filepath, "w+")
        try:
            f.write("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n")
            _progress(10)
            f.write("<%s>\n" % mediaType)
            _progress(19)
            f.write("\t<title>%s</title>\n" % title)
            _progress(28)
            if mediaType == "episodedetails" and tvShowName:
                f.write("\t<showtitle>%s</showtitle>\n" % tvShowName)
            _progress(37)
            f.write("\t<plot>%s</plot>\n" % plot)
            _progress(45)
            if aired:
                f.write("\t<aired>%s</aired>\n" % aired)
            _progress(54)
            if duration:
                f.write("\t<duration>%d</duration>\n" % int(round(int(duration) / 60.0)))
            _progress(63)
            if channel:
                f.write("\t<studio>%s</studio>\n" % channel)
            _progress(70)
            if genres:
                for genre in genres.split(","):
                    f.write("\t<genre>%s</genre>\n" % genre)
            _progress(80)
            if tags:
                for tag in tags.split(","):
                    f.write("\t<tag>%s</tag>\n" % tag)
            _progress(90)
            f.write("</%s>\n" % mediaType)
            _progress(100)
        except:
            myNotifyWarning(transl(30938))  #error
        finally:
            f.close()
    except (IOError, OSError) as e:
        myNotifyWarning(transl(30938))  #error


def recDownloadStream(manifestURL, targetFolder, targetFile,
                      pDialog=None, pDialogHeading=""):
    """Actually download the stream."""
    binPath = xbmcaddon.Addon().getAddonInfo('path') \
              + "/resources/lib/stream-recorder/"
    recCommand = "php AdobeHDS.php --manifest %s --outdir %s --outfile %s --delete" % (manifestURL, targetFolder, targetFile)

    recLog("binPath: " + binPath)
    recLog("recCommand: " + recCommand)
    try:
        #run command to record stream
        proc = subprocess.Popen(args=recCommand.split(" "),
                                cwd=binPath, stdout=subprocess.PIPE)
        if pDialog:
            #if progressDialog, calculate progress by analyzing command's output
            running = True #TODO error handling!!!
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
        return proc.returncode == 0
    except:
        recLog("The record command yielded an error!", xbmc.LOGERROR)
        return False


def recDownloadThumb(targetFilepath, sourceFileurl,
                     pDialog=None, pDialogHeading=""):
    """Download the given thumbnail and store it."""

    def _progress(percentage):
        if pDialog:
            pDialog.update(percentage, pDialogHeading, "", transl(30943))

    try:
        _progress(15)  #TODO get real progress(?)
        urllib.urlretrieve(sourceFileurl, targetFilepath)
    except:
        myNotifyWarning(cutStr(sourceFileurl, 25) + "\n" + transl(30942))  #error
    _progress(100)


def cutStr(string_, length_, ellips="..."):
    """Truncate the given string if its length is greater
       than the given one and append the given ellipsis string.
    """
    shortLen = (length_-len(ellips))
    if shortLen < 0:
        return ellips[:length_]
    else:
        return string_[:shortLen] + (ellips if string_[length_:] else \
                                     string_[shortLen:length_])

