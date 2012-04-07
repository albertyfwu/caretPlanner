import os

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

from google.appengine.api import users

import atom.data
import gdata.data
import gdata.contacts.client

import atom.http_core
import gdata.gauth

import logging

import json
import re

CONSUMER_KEY ='645332541228.apps.googleusercontent.com'
CONSUMER_SECRET = 'yNEKd0Dzp6LO9O4biURGotpZ'

contacts = ['a', 'ab', 'abc', 'abcd', 'abcde']

# create a client for handling Contacts API
contacts_client = gdata.contacts.client.ContactsClient(source='caretPlanner')

class MainHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            template_values = {
                'username': user.nickname(),
                'signOutUrl': users.create_logout_url('/')
            }

            path = os.path.join(os.path.dirname(__file__), 'index.html')
            self.response.out.write(template.render(path, template_values))
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
        
class ApiHandler(webapp.RequestHandler):
    def get(self):
#        self.response.out.write('temporarily disabled')
        # do we already have an access token?         
        try:            
            query = gdata.contacts.client.ContactsQuery()
            query.max_results = 100000
            feed = contacts_client.GetContacts(q = query)
            result = ''
        
            for i, entry in enumerate(feed.entry):
                if entry.name:
                    result += entry.name.full_name.text + ':'
                    for email in entry.email:
                        if email.primary and email.primary == 'true':
                            result += ' ' + email.address
                    result += '<br />'
    
            self.response.out.write(result)
        except:
            # if we don't have an access token already, get a request token
            request_token = contacts_client.GetOAuthToken(
                ['https://www.google.com/m8/feeds'],
                'http://caretplanner.appspot.com/oauth2callback',
                CONSUMER_KEY,
                CONSUMER_SECRET)
            
            # save the token
            gdata.gauth.AeSave(request_token, 'myKey')
            
            self.redirect(str(request_token.generate_authorization_url()))

class OAuthHandler(webapp.RequestHandler):
    def get(self):
        # recall the request token
        saved_request_token = gdata.gauth.AeLoad('myKey')
        request_token = gdata.gauth.AuthorizeRequestToken(saved_request_token, self.request.uri)
        
        # turn this into an access token
        access_token = contacts_client.GetAccessToken(request_token)
        gdata.gauth.AeSave(access_token, 'myAccessToken')

        contacts_client.auth_token = gdata.gauth.OAuthHmacToken(
            CONSUMER_KEY, CONSUMER_SECRET, access_token.token, access_token.token_secret, gdata.gauth.ACCESS_TOKEN)
        
        self.redirect('/api')
        
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

application = webapp.WSGIApplication(
    [('/', MainHandler),
     ('/about', AboutHandler),
     ('/api', ApiHandler),
     ('/oauth2callback.*', OAuthHandler)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
