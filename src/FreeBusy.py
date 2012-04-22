import datetime
from rfc3339 import rfc3339

class FreeBusy:
    def __init__(self, timesList = []):
        # timesList is a list of (start, end) tuples, where
        # start and end are datetime objects
        self.timesList = timesList
        
    def availableAt(self, startTime, endTime, constVar = 5):
        ## checks if the person who owns the calendar is available from 
        ## start + 5 minutes to end - 5 minutes
        startTimePlus = startTime + datetime.timedelta(0, 60 * constVar)
        endTimeMinus = endTime + datetime.timedelta(0, -60 * constVar)
        for (start, end) in self.timesList:
            if (startTimePlus < end and startTimePlus > start) or (endTimeMinus < end and endTimeMinus > start):
                return False
        return True
    
    def addEvent(self, start, end):
        self.timesList.append((start,end))
    
    def addEventFeed(self, eventFeed, startLimit, endLimit):
        for event in eventFeed:
            for when in event.when:
                start = rfcTodateTime(when.start)
                end = rfcTodateTime(when.end)
                if (start.time() >= startLimit and start.time() <= endLimit) \
                    or (end.time() >= startLimit and end.time() <= endLimit):
                    self.addEvent(start, end)
    def isEmpty(self):
        return self.timesList == []
    
def rfcTodateTime(rfc):
    year = int(rfc[0:4])
    month = int(rfc[5:7])
    day = int(rfc[8:10])
    hour = int(rfc[11:13])
    minute = int(rfc[14:16])
    # ignore seconds
    
    length = len(rfc)
    if rfc[length-1] == 'z' or rfc[length-1] == 'Z':
        return datetime.datetime(year, month, day, hour, minute)
    else:
        hour -= int(float(rfc[length-6:length-3]))
        return datetime.datetime(year, month, day, hour, minute)

    