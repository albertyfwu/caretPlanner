import os

import time
import datetime
from rfc3339 import rfc3339
import re

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

contacts = ['a', 'ab', 'abc', 'abcd', 'abcde']

contactsClients = {} # dictionary for ContactsClients
calendarClients = {} # dictionary for calendarClients

ownerToCalendars = {} # string owner email address -- > list of calendar IDs
calendarToOwners = {} # string calendar IDs --> list of owners
sharedToCalendars = {} # string email address --> list of calendar IDs he is shared with

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
    logging.info("dictAppend before")
    logging.info(d)
    if key in d and d[key] != None:
        d[key].append(value)
    else:
        d[key] = [value]
    logging.info("dictAppend after")
    logging.info(d)
        
def dictAdd(key, value, d):
    if key in d and d[key] != None:
        d[key] = d[key]+value
    else:
        d[key] = value

def RetrieveAclRule(username, calClient, cal_id):
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
        entry = RetrieveAclRule("socialplanner21@gmail.com", calClient, cal_id)
        roleValue = "http://schemas.google.com/gCal/2005#%s" % ("read")
        entry.role = gdata.acl.data.AclRole(value=roleValue)
        return calClient.Update(entry)
    except:
        return None
    
def removeAcl(calClient, cal_id):
    """Updates the Access Control Rule for the overlord account so that the the calendar
    with the given cal_id is removed from access"""
    try:
        entry = RetrieveAclRule("socialplanner21@gmail.com", calClient, cal_id)
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

def getEvents(calClient, calId, start_date, end_date): 
    """Returns list of events in the calendar that is between
    start_date and end_date, which are both in RFC3339 format"""
    
    Url = "https://www.google.com/calendar/feeds/"+calId+"/private/full"
    query = gdata.calendar.client.CalendarEventQuery(start_min=start_date, start_max=end_date)
    feed = calClient.CalendarQuery(uri = Url, q=query)
    return feed.entry
    
    
def calendarAvailability(calClient, calId, start_date, end_date):
    """Returns true if and only if # events within the time frame is 0 in
    calendar that is specified by calId. start_date and end_date are in
    RFC 3339 format"""
    
    Url = "https://www.google.com/calendar/feeds/"+calId+"/private/full"
    
    query = gdata.calendar.client.CalendarEventQuery(start_min=start_date, start_max=end_date)
    feed = calClient.CalendarQuery(uri = Url, q=query)
    length = feed.entry.length
    return length == 0

def contactAvailability(calClient, calList, start_date, end_date):
    for calId in calList:
        if calendarAvailability(calClient, calId, start_date, end_date) == False:
            return False
    return True


def FindTimes (calClient, contactsList, start_time, end_time, start_date, duration, date_duration = 14):
    """
    start_time and end_time are of types datetime.time
    start_date is of types datetime.date
    date_duration is n integer
    duration is an integer, representing the number of minutes the event will last
    contactsList is an array of email addresses
    
    returns list of start times that get the most people
    """
    bestTimes = {}
    currentStart = datetime.datetime(start_date.year, start_date.month, start_date.day, start_time.hour, start_time.minute)
    currentEnd = currentStart + datetime.timedelta(minutes = duration)
    for i in range(date_duration):
        while(currentEnd.time < end_time):
            currentStartRfc = rfc3339(currentStart)
            currentEndRfc = rfc3339(currentEnd)
            for contact in contactsList:
                if contact in ownerToCalendars:
                    if contactAvailability(calClient, ownerToCalendars[contact], currentStartRfc, currentEndRfc):
                        dictAdd(currentStart, 1, bestTimes)
    max_value = max[bestTimes.values()]
    if max_value == 0:
        return None
    output = []
    for key in bestTimes.keys():
        if (bestTimes[key] == max_value):
            output.append(key)
            
    return output

def findEvents(calClient, calId, text_query, start_date, end_date):
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
        eventfeed = getEvents(calClient, calId, start_date, end_date)
        for an_event in eventfeed.entry:
            m2 = p.match(an_event.title.text)
            if m2:
                if className == m2.group(1):
                    start,end = getWhen(an_event)
                    d = {'start': start, 'end': end, 'name': an_event.title.text}
                    output.append(d)
    else:
        return googleFindEvents(calClient, calId, text_query, start_date, end_date)
    
def googleFindEvents(calClient, calId, text_query, start_date, end_date):
    """ Uses google's search function to find events with similar names.
    Does not work for class names for some reason"""
    
    Url = "https://www.google.com/calendar/feeds/"+calId+"/private/full"
    query = gdata.calendar.client.CalendarEventQuery(text_query=text_query, start_min=start_date, start_max=end_date)
    feed = calClient.GetCalendarEventFeed(uri = Url, q=query)
    output = []
    
    for an_event in feed.entry:
        logging.info("start an_event for loop")
        logging.info(an_event.content.text)
        start, end = getWhen(an_event)
        d = {'start': start, 'end': end, 'name': an_event.title.text}
        output.append(d)
    
    return output

def getWhen(an_event):
    first = an_event.when[0]
    return first.start, first.end

def findAllEvents(username, text_query):
    logging.info("jsbach")
    logging.info(calendarClients)
    calClient = calendarClients[username]
    output = []
    logging.info("dvorak")
    logging.info(ownerToCalendars)
    for calId in ownerToCalendars[username]:
        output.extend(findEvents(calClient, calId, text_query))
        
    return output
        
def findEventsInContacts(calClient, contactsList, textQuery):
    output = []
    for contact in contactsList:
        if contact in ownerToCalendars:
            for calId in ownerToCalendars[contact]:
                output.extend(findEvents(calClient, calId, textQuery))
                
    return output

def findCommonEvents(calClient, email1, email2, start_date, end_date, constVar = 5):
    """start_date and end_date are RFC3339 format"""
    eventList1 = []
    eventList2 = []
    
    if email1 in ownerToCalendars:
        for calId in ownerToCalendars[email1]:
            eventList1.extend(getEvents(calClient, calId, start_date, end_date))
                              
    if email2 in ownerToCalendars:
        for calId in ownerToCalendars[email2]:
            eventList2.extend(getEvents(calClient, calId, start_date, end_date))
    
    output = []
    
    for an_event in eventList1:
        for an_event2 in eventList2:
            result = compareEvents(an_event, an_event2, constVar)
            if result:
                d = {'Name': an_event2.title.text, 'Start': result[0], 'End': result[1]}
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
    if rfc[length-1] == 'z':
        return datetime.datetime(year, month, day, hour, minute)
    else:
        hour += int(rfc[length-6:length-3])
        return datetime.datetime(year, month, day, hour, minute)


def compareTimes(t1, t2, constVar):
    """t1 and t2 are in rfc format"""
    delta = t2 - t1
    return abs(24*60*60*delta.days + delta.seconds) < constVar * 60  

class RegistrationHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if calendarClients.has_key(user.email()):
            logging.info("has calendar key")
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
                logging.info("cal_id here")
                logging.info(cal_id)
                dictAppend(user.email(), cal_id, ownerToCalendars)
                dictAppend(cal_id, user.email(), calendarToOwners)
                logging.info(cal_id)
                returned_rule = shareDefaultCalendar(calendar_client, cal_id)
            self.redirect("/")
        else:
            ownerToCalendars[user.email()] = []
            logging.info("calender else")
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
                                        contacts.append({'name':entry.name.full_name.text, 'email':email.address})
        #                            if email.primary and email.primary == 'true':
        #                                result += '     ' + email.address
        #                        result += '<br />'
                        
                        contacts.sort(key = lambda x: x['name'])
                        
                        logging.info(calendarClients)
                        stuffToPrint = findAllEvents('albertyfwu', '6\\.005 Lecture')
                        logging.info("Fuck mendelssohn")
                        logging.info(stuffToPrint)
                        logging.info(len(stuffToPrint))
                        logging.info("end fuck mendelssohn")
                
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
            
    def post(self):
        query = self.request.get('query')
        regex = '^' + query + '.*$'
        matches = [name for name in contacts if re.match(regex, name)]

        self.response.headers['Content-Type'] = 'application/json'
        result = json.dumps({'matches': matches})
        self.response.out.write(result)
        
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

        self.redirect('/')

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

class FindCommonEventsHandler(webapp.RequestHandler):
    def get(self):
        pass
    def post(self):
        jsonData = json.loads(self.request.get('jsonData'))
        # jsonData is a dictionary with 
        logging.info(jsonData)
        
    
class FindCommonTimesHandler(webapp.RequestHandler):
    def get(self):
        pass
    def post(self):
        pass

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
     ('/findCommonTimes', FindCommonTimesHandler)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
