import os

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

from google.appengine.api import users

import atom.data
import gdata.data
import gdata.contacts.client

import gdata.calendar.client

import atom.http_core
import gdata.gauth

import logging

import json
import re

CONSUMER_KEY = '645332541228-79g5u7m0fpm6tu07t4na6nlbspi7jq2j.apps.googleusercontent.com'
CONSUMER_SECRET = 'zN721xIL8yNRa4SKUFwKNp6b'

#CONSUMER_KEY ='645332541228.apps.googleusercontent.com'
#CONSUMER_SECRET = 'yNEKd0Dzp6LO9O4biURGotpZ'

contacts = ['a', 'ab', 'abc', 'abcd', 'abcde']

contactsClients = {} # dictionary for ContactsClients
calendarClients = {} # dictionary for calendarClients

class MainHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            if contactsClients.has_key(users.get_current_user()):
                contacts = []
                contacts_client = contactsClients[users.get_current_user()]
                query = gdata.contacts.client.ContactsQuery()
                query.max_results = 100000
                feed = contacts_client.GetContacts(q = query)
                
                for i, entry in enumerate(feed.entry):
                    if entry.name:
                        for email in entry.email:
                            if email.address.find('@gmail.com') != -1:
                                contacts.append({'name': entry.name.full_name.text, 'email': email.address})                
                contacts.sort(key = lambda contact: contact['name'])
                
                template_values = {
                    'username': user.nickname(),
                    'signOutUrl': users.create_logout_url('/'),
                    'contacts': contacts
                }
    
                path = os.path.join(os.path.dirname(__file__), 'index.html')
                self.response.out.write(template.render(path, template_values))
            else:
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

class AboutHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write()
        
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
        if calendarClients.has_key(users.get_current_user()):
            calendar_client = calendarClients[users.get_current_user()]
            query = gdata.calendar.client.CalendarEventQuery()
            query.max_results = 100000
            feed = calendar_client.GetAllCalendarsFeed(q = query)
            result = 'Printing all calendars: %s' % feed.title.text
            for i, a_calendar in zip(xrange(len(feed.entry)), feed.entry):
                result += '     ' + a_calendar + '      '
                result += '\t%s. %s' % (i, a_calendar.title.text,)
            
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
            

class OAuthHandler(webapp.RequestHandler):
    def get(self):
        # recall the request token
        saved_request_token = gdata.gauth.AeLoad('myContactsKey')
        if saved_request_token is None:
            gdata.gauth.AeDelete('myContactsKey')
            saved_request_token = gdata.gauth.AeLoad('myCalendarKey')
            gdata.gauth.AeDelete('myCalendarKey')
            flag = 0 # flag 2 --> calendar
            # get client
            client = calendarClients[users.get_current_user()]
        else: # if not none
            gdata.gauth.AeDelete('myContactsKey')
            flag = 1 # flag 1 --> contacts
            # get client
            client = contactsClients[users.get_current_user()]

        request_token = gdata.gauth.AuthorizeRequestToken(saved_request_token, self.request.uri)
        # turn this into an access token
        access_token = client.GetAccessToken(request_token)
        #gdata.gauth.AeSave(access_token, 'myAccessToken')
        client.auth_token = gdata.gauth.OAuthHmacToken(
        CONSUMER_KEY, CONSUMER_SECRET, access_token.token, access_token.token_secret, gdata.gauth.ACCESS_TOKEN)
        if flag == 1:
#            self.redirect('/api')
            self.redirect('/')
        else:
            self.redirect('/calendar')
        
           
        
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
        del contactsClients[users.get_current_user()]

application = webapp.WSGIApplication(
    [('/', MainHandler),
     ('/about', AboutHandler),
     ('/api', ApiHandler),
     ('/scheduleEvent', ScheduleEventHandler),
     ('/calendar', CalendarHandler),
     ('/oauth2callback.*', OAuthHandler)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
