import os

import time
import datetime
from rfc3339 import rfc3339
import re

import FreeBusy

from google.appengine.api import mail
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

from google.appengine.api import users

import atom.data
import gdata.data
import gdata.acl
import gdata.contacts.client

import gdata.calendar.client
import gdata.calendar.service

import atom.http_core
import gdata.gauth

import logging

import json
import re

class Debug:
    def __init__(self, name):
        self.name = name
        self.logs = []
    def info(self, object):
        self.logs.append(object)
    def getLogs(self):
        return self.logs
    
debug = Debug('poop')

runningLocally = True
# if True, runningLocally changes the oauthcallback to reflect localhost instead
# of caretPlanner
# if False, runningLocally uses caretPlanner and associated key

if runningLocally == True:
    CONSUMER_KEY = '645332541228-79g5u7m0fpm6tu07t4na6nlbspi7jq2j.apps.googleusercontent.com'
    CONSUMER_SECRET = 'zN721xIL8yNRa4SKUFwKNp6b'
    CONSUMER_KEY2 = '645332541228-s084s80t2vuk84vh3h95vpqa6dqkb830.apps.googleusercontent.com'
    CONSUMER_SECRET2 = 'idvG3PNPeWjlPKMqHvF7RTfA'
    calendarCallbackUrl = 'http://localhost:8080/oauth2calendarcallback'
    clientCallbackUrl = 'http://localhost:8080/oauth2callback'
    
else:
    CONSUMER_KEY ='645332541228.apps.googleusercontent.com'
    CONSUMER_SECRET = 'yNEKd0Dzp6LO9O4biURGotpZ'    
    CONSUMER_KEY2 = '645332541228-k6r9qt7esbhvsmts3rk1cqakrai2jvq1.apps.googleusercontent.com'
    CONSUMER_SECRET2 = 'weJQmMvxdKum8XGxMadzHNTz'
    calendarCallbackUrl = 'http://caretplanner.appspot.com/oauth2calendarcallback'
    clientCallbackUrl = 'http://caretplanner.appspot.com/oauth2callback'

contactsClients = {} # dictionary for ContactsClients
calendarClients = {} # dictionary for calendarClients

ownerToCalendars = {} # string owner email address -- > list of calendar IDs
calendarToOwners = {} # string calendar IDs --> list of owners
sharedToCalendars = {} # string email address --> list of calendar IDs he is shared with
timeZones = {} # string owner email address --> time zone (integer -12 to 12, representing how many hours ahead or behind he is)
defaultTZ = -4

overlordCalClient = gdata.calendar.client.CalendarClient(source = 'caretPlanner')
overlordCalClient.ClientLogin('socialplanner21@gmail.com', 'social21w785', overlordCalClient.source);
### Helper Functions for Dictionary Handling
def getCalendarOwners(CalID):
    if CalID in calendarToOwners:
        return calendarToOwners[CalID]
    else:
        return None
    
def getSharedCalendars(userAddress):
    if userAddress in sharedToCalendars:
        return sharedToCalendars[userAddress]
    else:
        return None
    
def getOwnedCalendars(userAddress):
    if userAddress in ownerToCalendars:
        return ownerToCalendars[userAddress]
    else:
        return None
    
def dictAppend(key, value, d):
    if key in d and d[key] != None:
        d[key].append(value)
    else:
        d[key] = [value]
        
def dictAdd(key, value, d):
    if key in d and d[key] != None:
        d[key] = d[key]+value
    else:
        d[key] = value

def getCalendarNames(calClient, calIdList):
    feed = calClient.GetOwnCalendarsFeed()
    calurl=[a_calendar.content.src for i, a_calendar in enumerate(feed.entry)]
    outputDict = {}
    for a_calendar in feed.entry:
        url = a_calendar.content.src
        urlSplitList = url.split("/")
        cal_id = urlSplitList[5]
        if cal_id in calIdList:
            outputDict[cal_id] = a_calendar.title.text
    return outputDict
    
        
def _RetrieveAclRule(username, calClient, cal_id):
    """Retrieves the entry associated with the Access Control Rule of the given username for
    the primary calendar of the calClient"""

    aclEntryUri = "http://www.google.com/calendar/feeds/"
    aclEntryUri += cal_id
    aclEntryUri += "/acl/full/user:%s" % (username)
    entry = calClient.GetCalendarAclEntry(aclEntryUri)
    return entry

def updateAcl(calClient, cal_id):
    """Updates the Access Control Rule for the overlord account for the calendar with the given
    calendar id cal_id"""
    try:
        entry = _RetrieveAclRule("socialplanner21@gmail.com", calClient, cal_id)
        roleValue = "http://schemas.google.com/gCal/2005#%s" % ("read")
        entry.role = gdata.acl.data.AclRole(value=roleValue)
        return calClient.Update(entry)
    except:
        return None
    
def removeAcl(calClient, cal_id):
    """Updates the Access Control Rule for the overlord account so that the the calendar
    with the given cal_id is removed from access"""
    try:
        entry = _RetrieveAclRule("socialplanner21@gmail.com", calClient, cal_id)
        calClient.Delete(entry.GetEditLink().href)
    except:
        return None
    
def shareDefaultCalendar(calClient, cal_id):
    """Shares the user's default calendar with the overlord account. First, it tries to add a new
    access control rule for the overlord account. If it is already there, then it tries to update 
    it."""
    
    try:
        rule = gdata.calendar.data.CalendarAclEntry()
        rule.scope = gdata.acl.data.AclScope(value="socialplanner21@gmail.com", type="user")
    
        roleValue = "http://schemas.google.com/gCal/2005#%s" % ("read")
        rule.role = gdata.acl.data.AclRole(value=roleValue)
        aclUrl = "https://www.google.com/calendar/feeds/"+cal_id+"/acl/full"
        return calClient.InsertAclEntry(rule, aclUrl)
    except gdata.client.RequestError:
        return updateAcl(calClient, cal_id)

def _getEvents(calClient, calId, start_date, end_date): 
    """Returns list of events in the calendar that is between
    start_date and end_date, which are both in RFC3339 format"""
    
    Url = "https://www.google.com/calendar/feeds/"+calId+"/private/full"
    query = gdata.calendar.client.CalendarEventQuery(start_min=start_date, start_max=end_date)
    query.max_results = 100000
    feed = calClient.GetCalendarEventFeed(uri = Url, q=query)
    return feed.entry
    
    
def _calendarAvailability(calClient, calId, start_date, end_date):
    """Returns true if and only if # events within the time frame is 0 in
    calendar that is specified by calId. start_date and end_date are in
    RFC 3339 format"""
    
    Url = "https://www.google.com/calendar/feeds/"+calId+"/private/full"
    
    query = gdata.calendar.client.CalendarEventQuery(start_min=start_date, start_max=end_date)
    feed = calClient.GetCalendarEventFeed(uri = Url, q=query)
    length = len(feed.entry)
    return length == 0

def contactAvailability(calClient, calList, start_date, end_date):
    for calId in calList:
        if _calendarAvailability(calClient, calId, start_date, end_date) == False:
            return False
    return True

def findTimes (calClient, contactsList, start_time, end_time, start_date, duration, date_duration = 14):
    """
    start_time and end_time are of types datetime.time
    start_date is of types datetime.date
    date_duration is n integer
    duration is an integer, representing the number of minutes the event will last
    contactsList is an array of email addresses
    
    returns list of start times that get the most people
    """
    
    freeBusyList = [] # list of freebusy objects
    
    for contact in contactsList:
        if contact in ownerToCalendars:
            freeBusy = FreeBusy.FreeBusy([])
            for calId in ownerToCalendars[contact]:
                earliest = datetime.datetime(start_date.year, start_date.month, start_date.day, start_time.hour, start_time.minute)
                lastDay = start_date + datetime.timedelta(date_duration)
                latest = datetime.datetime(lastDay.year, lastDay.month, lastDay.day, end_time.hour, end_time.minute)
                eventFeed = _getEvents(calClient, calId, rfc3339(earliest), rfc3339(latest))
                freeBusy.addEventFeed(eventFeed, start_time, end_time)
            if not freeBusy.isEmpty():
                freeBusyList.append(freeBusy)
    
    bestTimes = {}
    
    for i in range(date_duration):
        currentStart = datetime.datetime(start_date.year, start_date.month, start_date.day, start_time.hour, start_time.minute)
        currentStart += datetime.timedelta(i)
        currentEnd = currentStart + datetime.timedelta(minutes = duration)
        currentEnd += datetime.timedelta(i)
        while(currentEnd.time() < end_time):
            bestTimes[currentStart] = 0
            for freeBusy in freeBusyList:
                if freeBusy.availableAt(currentStart, currentEnd):
                    bestTimes[currentStart] += 1
            currentStart += datetime.timedelta(0, 900)
            currentEnd += datetime.timedelta(0, 900)
    
    max_value = max(bestTimes.values())
    logging.info(max_value)
    if max_value == 0:
        return None
    output = []
    for key in bestTimes.keys():
        if (bestTimes[key] == max_value):
            output.append(key)
    output.sort()
    return output

def findEventsInContactList(calClient, contactsList, text_query, start_date, end_date):
    """
    calClient - calendarClient
    contact - list of email addresses
    text_query - any string (Ex: 6.046, zoo trip, piano)
    start_date - date in RFC format (Ex: 2010-10-01T10:00:00-04:00)
    end_date - date in RFC format
    """
    output = []
    for contact in contactsList:
        temp = _findEventsInContact(calClient, contact, text_query, start_date, end_date)
        if temp != None:
            output.extend(temp)
    return output

def _findEventsInContact(calClient, contact, text_query, start_date, end_date):
    """
    calClient - calendarClient
    contact - contact email address
    text_query - any string (Ex: 6.046, zoo trip, piano)
    start_date - date in RFC format (Ex: 2010-10-01T10:00:00-04:00)
    end_date - date in RFC format
    """
    output = []
    if contact in ownerToCalendars:
        for calId in ownerToCalendars[contact]:
            output.extend(_findEvents(calClient, calId, text_query, start_date, end_date, contact))
        return output
    else:
        return None
def _findEvents(calClient, calId, text_query, start_date, end_date, owner):
    """
    calClient - calendarClient
    calId - URL id of calendar
    text_query - any string (Ex: 6.046, zoo trip, piano)
    start_date - date in RFC format (Ex: 2010-10-01T10:00:00-04:00)
    end_date - date in RFC format
    """
    
    p = re.compile('.*(\d+\w?.\d+\w?).*')
    m = p.match(text_query)
    if m:
        output = []
        className = m.group(1)
        eventfeed = _getEvents(calClient, calId, start_date, end_date)
        for an_event in eventfeed:
            m2 = p.match(an_event.title.text)
            if m2:
                if className == m2.group(1):
                    start,end = _getWhen(an_event)
                    d = {'startTime': start,
                         'endTime': end,
                         'name': an_event.title.text,
                         'owner': owner}
                    output.append(d)
        return output
    else:
        return _googleFindEvents(calClient, calId, text_query, start_date, end_date)
    
def _googleFindEvents(calClient, calId, text_query, start_date, end_date):
    """ Uses google's search function to find events with similar names.
    Does not work for class names for some reason"""
    
    Url = "https://www.google.com/calendar/feeds/"+calId+"/private/full"
    query = gdata.calendar.client.CalendarEventQuery(text_query=text_query, start_min=start_date, start_max=end_date)
    feed = calClient.GetCalendarEventFeed(uri = Url, q=query)
    output = []
    
    for an_event in feed.entry:
        start, end = _getWhen(an_event)
        d = {'startTime': start,
             'endTime': end,
             'name': an_event.title.text}
        output.append(d)
    
    return output

def _getWhen(an_event):
    first = an_event.when[0]
    return first.start, first.end

def findCommonEvents(calClient, emailList, start_date, end_date, constVar = 5):
    """ Requires emailList to have at least two emails
    start_date and end_date are in RFC3339 format
    constVar is how many minutes they can be late/leave early"""
        
    if len(emailList) < 2:
        return None
    else:
        logging.info('before tempOutput')
        tempOutput = findCommonEventsTwoPeople(calClient, emailList[0], emailList[1], start_date, end_date, constVar = 5)
        logging.info('after tempOutput')
        if len(emailList) == 2:
            debug.info('two people')
            output = []
            for event in tempOutput:
                debug.info('start of one event')
                debug.info(event.title.text)
                debug.info(event.when[0].start)
                debug.info(event.when[0].end)
                debug.info('end of one event')
                d = {'name': event.title.text,
                     'startTime': event.when[0].start,
                     'endTime': event.when[0].end}
                output.append(d)
            debug.info(output)
            return output
        else:
            for i in range(2, len(emailList)):
                output = []
                if emailList[i] in ownerToCalendars:
                    for calId in ownerToCalendars[emailList[i]]:
                        eventList = _getEvents(calClient, calId, start_date, end_date)
                        for an_event in tempOutput:
                            debug.info(an_event)
                            for an_event2 in eventList:
                                result = compareEvents(an_event, an_event2, constVar)
                                if result:
                                    d = {'name': an_event2.title.text,
                                         'startTime': result[0],
                                         'endTime': result[1]}
                                    output.append(d)
                                                    
                tempOutput = output
                if tempOutput == []:
                    return []
            return tempOutput
        
def findCommonEventsTwoPeople(calClient, email1, email2, start_date, end_date, constVar = 5):
    """start_date and end_date are RFC3339 format"""
    eventList1 = []
    eventList2 = []
    if email1 in ownerToCalendars:
        for calId in ownerToCalendars[email1]:
            # try threading to remove bottleneck?
#            def extendEventList1():
            eventList1.extend(_getEvents(calClient, calId, start_date, end_date))
#            Thread(target = extendEventList1).start()
#            eventList1.extend(_getEvents(calClient, calId, start_date, end_date))
                              
    if email2 in ownerToCalendars:
        for calId in ownerToCalendars[email2]:
            # try threading to remove bottleneck?
#            def extendEventList2():
            eventList2.extend(_getEvents(calClient, calId, start_date, end_date))
#            Thread(target = extendEventList2).start()
#            eventList2.extend(_getEvents(calClient, calId, start_date, end_date))
    
    output = []
    logging.info([x.title.text for x in eventList1])
    for an_event in eventList1:
        for an_event2 in eventList2:
            result = compareEvents(an_event, an_event2, constVar)
            if result:
                output.append(an_event)
    return output
                        

def compareEvents(event1, event2, var):    
    if not stringMatching(event1.title.text, event2.title.text):
        return False
    else:
        for when in event1.when:
            for when2 in event2.when:
                if compareTimes(when.start, when2.start, var) and compareTimes(when.end, when2.end, var):
                    return (when2.start, when2.end)
        return False
    
def stringMatching(str1, str2):
    p = re.compile('^\d+\w?.\d+\w?')
    if str1 is None or str2 is None:
        return False
    m1 = p.match(str1)
    m2 = p.match(str2)
    if m1 and m2:
        return m1.group() == m2.group()
    else:
        return str1 == str2

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
        hour = (hour - int(float(rfc[length-6:length-3]))) % 24
        return datetime.datetime(year, month, day, hour, minute)


def compareTimes(t1, t2, constVar):
    """t1 and t2 are in rfc format"""
    d1 = rfcTodateTime(t1)
    d2 = rfcTodateTime(t2)
    delta = d2 - d1
    return abs(24*60*60*delta.days + delta.seconds) < constVar * 60  

def scheduleEvent(calClient, calId, eventName, eventStart, eventEnd, contactsList, content = None, where = None):
    """
    calId - calendar ID
    eventName - string representing name of event
    eventStart - in rfc3339 format
    eventEnd - in rfc3339 format
    contactList - list of email addresses, must have @gmail.com
    """
    startDate = rfcTodateTime(eventStart)
    startDate = tzToGMT(startDate)
    start = rfc3339(startDate)
    
    endDate = rfcTodateTime(eventEnd)
    endDate = tzToGMT(endDate)
    end = rfc3339(endDate)
    url = "https://www.google.com/calendar/feeds/"+calId+"/private/full"
    event = gdata.calendar.data.CalendarEventEntry()
    event.title = atom.data.Title(text=eventName)
    event.content = atom.data.Content(text=content)
    event.where.append(gdata.data.Where(value=where))
    event.when.append(gdata.data.When(start=start,
          end=end))
    for contact in contactsList:
        guest = gdata.calendar.Who()
        guest.email = contact ## This must have @gmail.com
        event.who.append(guest)
    new_event = calClient.InsertEvent(event, url)
    
    return new_event

    
def makeMessage(eventName, start, end, nickName):
    subject = nickName + " has invited you to " + eventName
    body="""
    Dear Friend:
    
    %s has invited you to an event called %s from %s 
    to %s. Click the button below to accept the invitation.
    
    socialPlanner
    """
class RegistrationHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if calendarClients.has_key(user.email()):
            # Add time zone
            timeZones[user.email()] = defaultTZ
            
            calendar_client = calendarClients[user.email()]
            query = gdata.calendar.client.CalendarEventQuery()
            query.max_results = 100000
            
            feed = calendar_client.GetOwnCalendarsFeed(q = query)
#            ownerToCalendars[user.email()] = [] # to make sure that an entry is there so it doesn't run infinite loop
            #for a_calendar in feed.entry:
            calurl=[a_calendar.content.src for i, a_calendar in enumerate(feed.entry)]
            for url in calurl:
                urlSplitList = url.split("/")
                cal_id = urlSplitList[5]
                dictAppend(user.email(), cal_id, ownerToCalendars)
                dictAppend(cal_id, user.email(), calendarToOwners)
                returned_rule = shareDefaultCalendar(calendar_client, cal_id)
            self.redirect("/")
        else:
            if user.email() not in ownerToCalendars:
                ownerToCalendars[user.email()] = []
            calendar_client = gdata.calendar.client.CalendarClient(source='caretPlanner')
            calendarClients[users.get_current_user().email()] = calendar_client
            # if we don't have an access token already, get a request token
            request_token = calendar_client.GetOAuthToken(
                ['http://www.google.com/calendar/feeds'],
                calendarCallbackUrl,
                CONSUMER_KEY2,
                CONSUMER_SECRET2)
            
            # save the token
            gdata.gauth.AeSave(request_token, 'myCalendarKey')
            
            self.redirect(str(request_token.generate_authorization_url()))
            
### this gets called when running main
class MainHandler(webapp.RequestHandler):
    def get(self):
        for key in ownerToCalendars.keys():
            logging.info(key)
            
        user = users.get_current_user()        
        if user: # if logged in
            if user.email() not in ownerToCalendars: # if user is not registered
                # show the user the registration page
                path = os.path.join(os.path.dirname(__file__), 'registration.html')
                self.response.out.write(template.render(path, {}))
#                self.response.out.write('')
#                if calendarClients.has_key(users.get_current_user().email()):
#                    logging.info("has calendar key")
#                    calendar_client = calendarClients[users.get_current_user().email()]
#                    query = gdata.calendar.client.CalendarEventQuery()
#                    query.max_results = 100000
#                    
#                    feed = calendar_client.GetOwnCalendarsFeed(q = query)
#                    #ownerToCalendars[user.email()] = [] # to make sure that an entry is there so it doesn't run infinite loop
#                    #for a_calendar in feed.entry:
#                    calurl=[a_calendar.content.src for i, a_calendar in enumerate(feed.entry)]
#                    for url in calurl:
#                        urlSplitList = url.split("/")
#                        cal_id = urlSplitList[5]
#                        logging.info("cal_id here")
#                        logging.info(cal_id)
#                        dictAppend(user.email(), cal_id, ownerToCalendars)
#                        dictAppend(cal_id, user.email(), calendarToOwners)
#                        logging.info(cal_id)
#                        returned_rule = shareDefaultCalendar(calendar_client, cal_id)
#                    self.redirect("/")
#                else:
#                    logging.info("calender else")
#                    calendar_client = gdata.calendar.client.CalendarClient(source='caretPlanner')
#                    calendarClients[users.get_current_user().email()] = calendar_client
#                    # if we don't have an access token already, get a request token
#                    request_token = calendar_client.GetOAuthToken(
#                        ['http://www.google.com/calendar/feeds'],
#                        calendarCallbackUrl,
#                        CONSUMER_KEY2,
#                        CONSUMER_SECRET2)
#                    
#                    # save the token
#                    gdata.gauth.AeSave(request_token, 'myCalendarKey')
#                    
#                    self.redirect(str(request_token.generate_authorization_url()))
            else: ## if user already registered
                if contactsClients.has_key(users.get_current_user().email()): # if a contacts client is already available for current user
                    # use contact client that's available
                        for key in ownerToCalendars.keys():
                            logging.info(key)
                        contacts = []
                        contacts_client = contactsClients[users.get_current_user().email()]
                        query = gdata.contacts.client.ContactsQuery()
                        query.max_results = 100000
                        feed = contacts_client.GetContacts(q = query)
                        
                        for i, entry in enumerate(feed.entry):
                            if entry.name:
                                for email in entry.email:
                                    if email.address.find('@gmail.com') != -1:
                                        if email.address in ownerToCalendars and email.address != users.get_current_user().email():
                                            contacts.append({'name':entry.name.full_name.text, 'email':email.address})
        #                            if email.primary and email.primary == 'true':
        #                                result += '     ' + email.address
        #                        result += '<br />'
                        
                        contacts.sort(key = lambda x: x['name'])
                
        #                self.response.out.write(result)
                        template_values = {
                            'username': users.get_current_user().nickname(),
                            'signOutUrl': users.create_logout_url('/'),
                            'contacts': contacts
                        }
            
                        path = os.path.join(os.path.dirname(__file__), 'index.html')
                        self.response.out.write(template.render(path, template_values))
                    
                else:
                    logging.info("need contacts client")
                    contacts_client = gdata.contacts.client.ContactsClient(source='caretPlanner')
                    contactsClients[users.get_current_user().email()] = contacts_client
                    # if we don't have an access token already, get a request token
                    request_token = contacts_client.GetOAuthToken(
                        ['https://www.google.com/m8/feeds'],
                        clientCallbackUrl,
                        CONSUMER_KEY,
                        CONSUMER_SECRET)
                
                    # save the token
                    gdata.gauth.AeSave(request_token, 'myContactsKey')
                    
                    self.redirect(str(request_token.generate_authorization_url()))
        else:
            self.redirect(users.create_login_url(self.request.uri))
        
#class RegistrationHandler
#    def get(self):
#        self.response.out.write("hi")
##        if calendarClients.has_key(users.get_current_user()):
##            calendar_client = calendarClients[users.get_current_user()]
#            rule = {
#                'scope': {
#                          'type': 'user',
#                          'value': 'socialplanner21@gmail.com',
#                          },
#                'role': 'reader'
#            }
#
#            created_rule = service.acl().insert(calendarId='primary', body=rule).execute()
#            query = gdata.calendar.client.CalendarEventQuery()
#            query.max_results = 100000
#            feed = calendar_client.GetAllCalendarsFeed(q = query)
#            result = 'Printing all calendars: %s' % feed.title.text
#            for i, a_calendar in zip(xrange(len(feed.entry)), feed.entry):
#                result += '\t%s. %s' % (i, a_calendar.title.text,)
#            
#            self.response.out.write(result)
#            
#        else:
#            calendar_client = gdata.calendar.client.CalendarClient(source='caretPlanner')
#            calendarClients[users.get_current_user()] = calendar_client
#             if we don't have an access token already, get a request token
#            request_token = calendar_client.GetOAuthToken(
#                ['http://www.google.com/calendar/feeds'],
#                'http://caretplanner.appspot.com/oauth2callback',
#                'http://localhost:8080/oauth2callback',
#                CONSUMER_KEY,
#                CONSUMER_SECRET)
#            
#             save the token
#            gdata.gauth.AeSave(request_token, 'myRegistrationKey')
#            
#            self.redirect(str(request_token.generate_authorization_url()))
        


class AboutHandler(webapp.RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'about.html')
        self.response.out.write(template.render(path, {}))
        
class ScheduleEventHandler(webapp.RequestHandler):
    def get(self):
        pass
    def post(self):
        contacts = json.loads(self.request.get('contacts'))
        # contacts is a list of Gmail email addresses
        # do stuff with these contacts
        # algorithm goes here
        result = "The following times are good for scheduling an event:\n" + \
            "2/15 3:00PM - 4:00PM\n" + \
            "2/20 4:45PM - 6:15PM"
        # end do stuff with these contacts
        self.response.out.write(result)

class CalendarHandler(webapp.RequestHandler):
    def get(self):
        if calendarClients.has_key(users.get_current_user().email()):
            calendar_client = calendarClients[users.get_current_user().email()]
            query = gdata.calendar.client.CalendarEventQuery()
            query.max_results = 100000
            
            feed = calendar_client.GetAllCalendarsFeed(q = query)
            result = 'Printing all calendars: %s' % feed.title.text
            
            for i, a_calendar in zip(xrange(len(feed.entry)), feed.entry):
                result += '\t%s. %s' % (i, a_calendar.get_id())
            
            self.response.out.write(result)
            
        else:
            calendar_client = gdata.calendar.client.CalendarClient(source='caretPlanner')
            calendarClients[users.get_current_user().email()] = calendar_client
            # if we don't have an access token already, get a request token
            request_token = calendar_client.GetOAuthToken(
                ['http://www.google.com/calendar/feeds'],
                calendarCallbackUrl,
                CONSUMER_KEY,
                CONSUMER_SECRET)
            
            # save the token
            gdata.gauth.AeSave(request_token, 'myCalendarKey')
            
            self.redirect(str(request_token.generate_authorization_url()))


class ApiHandler(webapp.RequestHandler):
    def get(self):
#        self.response.out.write('temporarily disabled')
        # do we already have an access token?
        if contactsClients.has_key(users.get_current_user().email()):
            contacts_client = contactsClients[users.get_current_user().email()]
            query = gdata.contacts.client.ContactsQuery()
            query.max_results = 100000
            feed = contacts_client.GetContacts(q = query)
            result = ''
            
            for i, entry in enumerate(feed.entry):
                if entry.name:
                    result += entry.name.full_name.text + ':'
                    for email in entry.email:
                        if email.primary and email.primary == 'true':
                            result += '     ' + email.address
                    result += '<br />'
    
            self.response.out.write(result)
        else:
            contacts_client = gdata.contacts.client.ContactsClient(source='caretPlanner')
            contactsClients[users.get_current_user().email()] = contacts_client
            # if we don't have an access token already, get a request token
            request_token = contacts_client.GetOAuthToken(
                ['https://www.google.com/m8/feeds'],
                clientCallbackUrl,
                CONSUMER_KEY,
                CONSUMER_SECRET)
            
            # save the token
            gdata.gauth.AeSave(request_token, 'myContactsKey')
            
            self.redirect(str(request_token.generate_authorization_url()))
            
class OAuthCalendarHandler(webapp.RequestHandler):
    def get(self):
        # recall the request token
        saved_request_token = gdata.gauth.AeLoad('myCalendarKey')
        gdata.gauth.AeDelete('myCalendarKey')
        # get client
        logging.info(calendarClients)
        client = calendarClients[users.get_current_user().email()]

        request_token = gdata.gauth.AuthorizeRequestToken(saved_request_token, self.request.uri)
        # turn this into an access token
        access_token = client.GetAccessToken(request_token)
        #gdata.gauth.AeSave(access_token, 'myAccessToken')
        client.auth_token = gdata.gauth.OAuthHmacToken(
        CONSUMER_KEY2, CONSUMER_SECRET2, access_token.token, access_token.token_secret, gdata.gauth.ACCESS_TOKEN)

        self.redirect('/registration')

class OAuthHandler(webapp.RequestHandler):
    def get(self):
        # recall the request token
        saved_request_token = gdata.gauth.AeLoad('myContactsKey')
        gdata.gauth.AeDelete('myContactsKey')
        # get client
        client = contactsClients[users.get_current_user().email()]

        request_token = gdata.gauth.AuthorizeRequestToken(saved_request_token, self.request.uri)
        # turn this into an access token
        access_token = client.GetAccessToken(request_token)
        #gdata.gauth.AeSave(access_token, 'myAccessToken')
        client.auth_token = gdata.gauth.OAuthHmacToken(
        CONSUMER_KEY, CONSUMER_SECRET, access_token.token, access_token.token_secret, gdata.gauth.ACCESS_TOKEN)

        self.redirect('/')

class SignOutHandler(webapp.RequestHandler):
    def get(self):
        pass
    def post(self):
        if users.get_current_user().email() in contactsClients:
            del contactsClients[users.get_current_user().email()]
        if users.get_current_user().email() in calendarClients:
            del calendarClients[users.get_current_user().email()]

# takes a string datetime like '08/20/2012 06:52 pm' and converts it into RFC format
def textDateTimeToRfc(stringDate):
    dateTimeList = stringDate.split(' ')
    dateList = dateTimeList[0].split('/')
    timeList = dateTimeList[1].split(':')
    iDateList = [int(entry) for entry in dateList] #[8, 20, 2012]
    iTimeList = [int(entry) for entry in timeList] #[6, 52]
    pythonDate = datetime.datetime(iDateList[2], # year
                               iDateList[0], # month
                               iDateList[1], # day
                               iTimeList[0] + 12 * (dateTimeList[2] == 'pm' and iTimeList[0] != 12), # hour
                               iTimeList[1])
    return rfc3339(pythonDate)

def textDateToDate(stringDate):
    dateList = stringDate.split('/')
    iDateList = [int(entry) for entry in dateList]
    pythonDate = datetime.date(iDateList[2],
                               iDateList[0],
                               iDateList[1])
    return pythonDate

def textDateToDateTime(stringDate):
    dateList = stringDate.split('/')
    iDateList = [int(entry) for entry in dateList]
    pythonDateTime = datetime.datetime(iDateList[2],
                               iDateList[0],
                               iDateList[1],
                               0,
                               0)
    return pythonDateTime

def textDateTimeToDateTime(stringDate):
    dateTimeList = stringDate.split(' ')
    dateList = dateTimeList[0].split('/')
    timeList = dateTimeList[1].split(':')
    iDateList = [int(entry) for entry in dateList] #[8, 20, 2012]
    iTimeList = [int(entry) for entry in timeList] #[6, 52]
    pythonDateTime = datetime.datetime(iDateList[2], # year
                               iDateList[0], # month
                               iDateList[1], # day
                               iTimeList[0] + 12 * (dateTimeList[2] == 'pm' and iTimeList[0] != 12), # hour
                               iTimeList[1])
    return pythonDateTime

# add in time zone stuff here later
def rfcToDateTimeText(rfc):
    year = int(rfc[0:4])
    month = int(rfc[5:7])
    day = int(rfc[8:10])
    hour = int(rfc[11:13])
    minute = int(rfc[14:16])
    # ignore seconds
    
    length = len(rfc)
    if rfc[length-1] == 'z' or rfc[length-1] == 'Z':
        logging.info('z')
    else:
        hour = (hour - int(float(rfc[length-6:length-3]))) % 24
    if hour > 12:
        hourText = str(hour - 12).zfill(2)
        hourSuffix = 'pm'
    else:
        hourText = str(hour).zfill(2)
        hourSuffix = 'am'
    dateTimeText = rfc[5:7] + '/' + \
                   rfc[8:10] + '/' + \
                   rfc[0:4] + ' ' + \
                   hourText + ':' + \
                   rfc[14:16] + ' ' + \
                   hourSuffix
    return dateTimeText

def tzToGMT(dateTime, timezone):
    return dateTime + datetime.timedelta(hours = -timezone)
def GMTTotz(dateTime, timezone):
    return dateTime + datetime.timedelta(hours = timezone)

class FindCommonEventsHandler(webapp.RequestHandler):
    def get(self):
        pass
    def post(self):
        jsonData = json.loads(self.request.get('jsonData'))
        startTime = jsonData['startTime'] # in mm/dd/yyyy format
        endTime = jsonData['endTime'] # in mm/dd/yyyy format
        friends = jsonData['friends'] # in list format of @gmail.com addresses
        
        user = users.get_current_user()
        
        email1 = user.email()
#        emailList = [friend[0:-len('@gmail.com')] for friend in friends]
        emailList = friends
        emailList.append(email1)
        
        start_time_date = textDateTimeToDateTime(startTime)
        end_time_date = textDateTimeToDateTime(endTime)
        rfcStartTime = rfc3339(tzToGMT(start_time_date, timeZones[email1]))
        rfcEndTime = rfc3339(tzToGMT(end_time_date, timeZones[email1]))

        logging.info('emailList')
        logging.info(emailList)
        logging.info(rfcStartTime)
        logging.info(rfcEndTime)
        logging.info('endEmailList')
        
        # the following line is the bottleneck
        commonEvents = findCommonEvents(overlordCalClient, emailList, rfcStartTime, rfcEndTime)
        
        logging.info('what is the user')
        logging.info(user)
        
        logging.info('what are the events')
        logging.info(commonEvents)
        
        
        self.response.headers['Content-Type'] = 'application/json'
        result = json.dumps(commonEvents)
        self.response.out.write(result)
#        logging.info(jsonData)
        
    
class FindCommonTimesHandler(webapp.RequestHandler):
    def get(self):
        pass
    def post(self):
        jsonData = json.loads(self.request.get('jsonData'))
        startTime = jsonData['startTime']
        endTime = jsonData['endTime'] # in mm/dd/yyyy format
        startDate = jsonData['startDate']
        dateDuration = jsonData['dateDuration']
        timesDuration = jsonData['timesDuration']
        friends = jsonData['friends'] # in list format of @gmail.com addresses
        
        user = users.get_current_user()
        
        email1 = user.email()
        emailList = friends
        emailList.append(email1)
        
        startTimeList = startTime.split(' ')
        startTimeHMList = startTimeList[0].split(':')
        startTimePy = datetime.time(int(startTimeHMList[0]) \
                                    + 12 * (startTimeList[1] == 'pm' and startTimeHMList[0] != 12),
                                    int(startTimeHMList[1]))
        
        endTimeList = endTime.split(' ')
        endTimeHMList = endTimeList[0].split(':')
        endTimePy = datetime.time(int(endTimeHMList[0]) \
                                  + 12 * (endTimeList[1] == 'pm' and endTimeHMList[0] != 12),
                                  int(endTimeHMList[1]))
        
        startDatePy = textDateToDateTime(startDate)
        
        dateDurationInt = int(dateDuration)
        
        timesDurationList = timesDuration.split(':')
        timesDurationInt = int(timesDurationList[0]) * 60 + int(timesDurationList[1])
                
        commonTimes = findTimes(overlordCalClient, emailList, startTimePy, endTimePy,
                                startDatePy, timesDurationInt, dateDurationInt)
        output = []
        rfcCommonTimes = []
        if commonTimes != None:                        
            rfcCommonTimes = []
            for commonTime in commonTimes:
                # commonTime is a python datetime object
                startTime = rfcToDateTimeText(rfc3339(commonTime))
                endTime = rfcToDateTimeText(rfc3339(commonTime + datetime.timedelta(minutes=timesDurationInt)))
                d = {'startTime': startTime,
                     'endTime': endTime}
                rfcCommonTimes.append(d)
            logging.info(rfcCommonTimes)
        
        self.response.headers['Content-Type'] = 'application/json'
        result = json.dumps(rfcCommonTimes)
        self.response.out.write(result)
        

class FindEventsHandler(webapp.RequestHandler):
    def get(self):
        pass
    def post(self):
        logging.info("Start findEventsHandler")
        jsonData = json.loads(self.request.get('jsonData'))
        startTime = jsonData['startTime'] # in mm/dd/yyyy TT:TT format
        endTime = jsonData['endTime'] # in mm/dd/yyyy TT:TT format
        eventQuery = jsonData['eventQuery']
        friends = jsonData['friends'] # in list format of @gmail.com addresses
        
        user = users.get_current_user()
        
        email1 = user.email()
        emailList = friends
        
        start_time_date = textDateTimeToDateTime(startTime)
        end_time_date = textDateTimeToDateTime(endTime)
        rfcStartTime = rfc3339(tzToGMT(start_time_date, timeZones[email1]))
        rfcEndTime = rfc3339(tzToGMT(end_time_date, timeZones[email1]))
        
        logging.info('emailList')
        logging.info(emailList)
        logging.info('endEmailList')
        # look at FindCommonEventsHandler's post(self): for an example        
        events = findEventsInContactList(overlordCalClient, emailList, eventQuery, rfcStartTime, rfcEndTime)
        
        logging.info('what is the user')
        logging.info(user)
        
        logging.info('what are the events')
        logging.info(events)
        
        self.response.headers['Content-Type'] = 'application/json'
        result = json.dumps(events)
        self.response.out.write(result)
        
class ScheduleAnEventHandler(webapp.RequestHandler):
    def get(self):
        pass
    def post(self):
        jsonData = json.loads(self.request.get('jsonData'))
        startTime = jsonData['startTime'] # in mm/dd/yyyy TT:TT pm format
        endTime = jsonData['endTime'] # in mm/dd/yyyy TT:TT pm format
        calId = jsonData['calId']
        eventName = jsonData['eventName']
        friends = jsonData['friends']
        
        startTimeRfc = textDateTimeToRfc(startTime)
        endTimeRfc = textDateTimeToRfc(endTime)
        
        client = calendarClients[users.get_current_user().email()]   
        
        if scheduleEvent(client, calId, eventName, startTimeRfc, endTimeRfc, friends):
            self.response.out.write('success')
        else:
            self.response.out.write('failure')
                 
class PoopHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write(ownerToCalendars)
        
class DebugHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write(debug.getLogs())
        
application = webapp.WSGIApplication(
    [('/', MainHandler),
     ('/about', AboutHandler),
     ('/api', ApiHandler),
     ('/scheduleEvent', ScheduleEventHandler),
     ('/calendar', CalendarHandler),
     ('/registration', RegistrationHandler),
     ('/oauth2callback.*', OAuthHandler),
     ('/oauth2calendarcallback.*', OAuthCalendarHandler),
     ('/findCommonEvents', FindCommonEventsHandler),
     ('/findCommonTimes', FindCommonTimesHandler),
     ('/findEvents', FindEventsHandler),
     ('/scheduleAnEvent', ScheduleAnEventHandler),
     ('/poop', PoopHandler),
     ('/debug', DebugHandler)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
