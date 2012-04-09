import os

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

from google.appengine.api import users

import atom.data
import gdata.data
import gdata.acl
import gdata.contacts.client

import gdata.calendar.client

import atom.http_core
import gdata.gauth

import logging

import json
import re

CONSUMER_KEY = '645332541228-79g5u7m0fpm6tu07t4na6nlbspi7jq2j.apps.googleusercontent.com'
CONSUMER_SECRET = 'zN721xIL8yNRa4SKUFwKNp6b'

CONSUMER_KEY2 = '645332541228-s084s80t2vuk84vh3h95vpqa6dqkb830.apps.googleusercontent.com'
CONSUMER_SECRET2 = 'idvG3PNPeWjlPKMqHvF7RTfA'

#CONSUMER_KEY ='645332541228.apps.googleusercontent.com'
#CONSUMER_SECRET = 'yNEKd0Dzp6LO9O4biURGotpZ'

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
    if key in d:
        d[key] = d[key].append(value)
    else:
        d[key] = [value]


### this gets called when running main
class MainHandler(webapp.RequestHandler):
    def get(self):
        for key in ownerToCalendars.keys():
            logging.info(key)
            
        user = users.get_current_user()
        
        if user: # if logged in
            if not ownerToCalendars.has_key(user.email()): # if user is not registered
                logging.info("asd;lkjfffffffffffffffffffffffffffffff")
                if calendarClients.has_key(users.get_current_user()):
                    logging.info("has calendar key")
                    calendar_client = calendarClients[users.get_current_user()]
                    query = gdata.calendar.client.CalendarEventQuery()
                    query.max_results = 100000
                    
                    feed = calendar_client.GetOwnCalendarsFeed(q = query)
                    #ownerToCalendars[user.email()] = [] # to make sure that an entry is there so it doesn't run infinite loop
                    #for a_calendar in feed.entry:
                    a_calendar = feed.entry[0]
                    dictAppend(user.email(), a_calendar.get_id, ownerToCalendars)
                    dictAppend(a_calendar.get_id, user.email(), calendarToOwners)
                    rule = gdata.calendar.data.CalendarAclEntry()
                    rule.scope = gdata.acl.data.AclScope(value="socialplanner21@gmail.com", type="user")

                    roleValue = "http://schemas.google.com/gCal/2005#%s" % ("read")
                    rule.role = gdata.acl.data.AclRole(value=roleValue)
                    aclUrl = "https://www.google.com/calendar/feeds/default/acl/full"
                    returned_rule = calendar_client.InsertAclEntry(rule, aclUrl)
                        
#                        aclEntryUri = "http://www.google.com/calendar/feeds/"
#                        aclEntryUri += "default/acl/full/user:%s" % ("socialplanner21@gmail.com")
#                        entry = calendar_client.GetCalendarAclEntry(aclEntryUri)
#                        roleValue = "http://schemas.google.com/gCal/2005#%s" % ("read")
#                        entry.role = gdata.acl.data.AclRole(value=roleValue)
#                        returned_rule = calendar_client.Update(entry)
                else:
                    logging.info("calender else")
                    calendar_client = gdata.calendar.client.CalendarClient(source='caretPlanner')
                    calendarClients[users.get_current_user()] = calendar_client
                    # if we don't have an access token already, get a request token
                    request_token = calendar_client.GetOAuthToken(
                        ['http://www.google.com/calendar/feeds'],
        #                'http://caretplanner.appspot.com/oauth2callback',
                        'http://localhost:8080/oauth2calendarcallback',
                        CONSUMER_KEY2,
                        CONSUMER_SECRET2)
                    
                    # save the token
                    gdata.gauth.AeSave(request_token, 'myCalendarKey')
                    
                    self.redirect(str(request_token.generate_authorization_url()))
            else: ## if user already registered
                if contactsClients.has_key(users.get_current_user()): # if a contacts client is already available for current user
                    # use contact client that's available
                        for key in ownerToCalendars.keys():
                            logging.info(key)
                        contacts = []
                        contacts_client = contactsClients[users.get_current_user()]
                        query = gdata.contacts.client.ContactsQuery()
                        query.max_results = 100000
                        feed = contacts_client.GetContacts(q = query)
                        
                        for i, entry in enumerate(feed.entry):
                            if entry.name:
                                for email in entry.email:
                                    if email.address.find('@gmail.com') != -1:
                                        contacts.append(entry.name.full_name.text)
        #                            if email.primary and email.primary == 'true':
        #                                result += '     ' + email.address
        #                        result += '<br />'
                        
                        contacts.sort()
                
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
                    contactsClients[users.get_current_user()] = contacts_client
                    # if we don't have an access token already, get a request token
                    request_token = contacts_client.GetOAuthToken(
                        ['https://www.google.com/m8/feeds'],
    #                    'http://caretplanner.appspot.com/oauth2callback',
                        'http://localhost:8080/oauth2callback',
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
#        
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
        self.response.out.write()

class CalendarHandler(webapp.RequestHandler):
    def get(self):
        if calendarClients.has_key(users.get_current_user()):
            calendar_client = calendarClients[users.get_current_user()]
            query = gdata.calendar.client.CalendarEventQuery()
            query.max_results = 100000
            
            feed = calendar_client.GetAllCalendarsFeed(q = query)
            result = 'Printing all calendars: %s' % feed.title.text
            
            for i, a_calendar in zip(xrange(len(feed.entry)), feed.entry):
                result += '\t%s. %s' % (i, a_calendar.get_id())
            
            self.response.out.write(result)
            
        else:
            calendar_client = gdata.calendar.client.CalendarClient(source='caretPlanner')
            calendarClients[users.get_current_user()] = calendar_client
            # if we don't have an access token already, get a request token
            request_token = calendar_client.GetOAuthToken(
                ['http://www.google.com/calendar/feeds'],
#                'http://caretplanner.appspot.com/oauth2callback',
                'http://localhost:8080/oauth2callback',
                CONSUMER_KEY,
                CONSUMER_SECRET)
            
            # save the token
            gdata.gauth.AeSave(request_token, 'myCalendarKey')
            
            self.redirect(str(request_token.generate_authorization_url()))


class ApiHandler(webapp.RequestHandler):
    def get(self):
#        self.response.out.write('temporarily disabled')
        # do we already have an access token?
        if contactsClients.has_key(users.get_current_user()):
            contacts_client = contactsClients[users.get_current_user()]
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
            contactsClients[users.get_current_user()] = contacts_client
            # if we don't have an access token already, get a request token
            request_token = contacts_client.GetOAuthToken(
                ['https://www.google.com/m8/feeds'],
#                'http://caretplanner.appspot.com/oauth2callback',
                'http://localhost:8080/oauth2callback',
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
        client = calendarClients[users.get_current_user()]

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
        client = contactsClients[users.get_current_user()]

        request_token = gdata.gauth.AuthorizeRequestToken(saved_request_token, self.request.uri)
        # turn this into an access token
        access_token = client.GetAccessToken(request_token)
        #gdata.gauth.AeSave(access_token, 'myAccessToken')
        client.auth_token = gdata.gauth.OAuthHmacToken(
        CONSUMER_KEY, CONSUMER_SECRET, access_token.token, access_token.token_secret, gdata.gauth.ACCESS_TOKEN)

        self.redirect('/')
           
        
#        result = ''
#        query = gdata.contacts.client.ContactsQuery()
#        query.max_results = 100000
#        feed = contacts_client.GetContacts(q = query)
#        for i, entry in enumerate(feed.entry):
#            if entry.name:
#                result += entry.name.full_name.text + ':'
#                for email in entry.email:
#                    if email.primary and email.primary == 'true':
#                        result += ' ' + email.address
#                result += '<br />'
#
#        self.response.out.write(result)

class SignOutHandler(webapp.RequestHandler):
    def get(self):
        pass
    def post(self):
        if users.get_current_user() in contactsClients:
            del contactsClients[users.get_current_user()]
        if users.get_current_user() in calendarClients:
            del calendarClients[users.get_current_user()]

application = webapp.WSGIApplication(
    [('/', MainHandler),
     ('/about', AboutHandler),
     ('/api', ApiHandler),
     ('/calendar', CalendarHandler),
#     ('/registration', RegistrationHandler),
     ('/oauth2callback.*', OAuthHandler),
     ('/oauth2calendarcallback.*', OAuthCalendarHandler)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
