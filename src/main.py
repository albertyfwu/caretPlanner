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

token = None

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
        contacts_client = gdata.contacts.client.ContactsClient(source='caretPlanner')
        
        token = gdata.gauth.OAuth2Token(client_id='TYPE CLIENT ID HERE',
                                        client_secret='TYPE CLIENT SECRET HERE',
                                        scope='https://www.google.com/m8/feeds',
                                        user_agent='caretplanner')
        logging.info('got here')
        logging.info(type(token))
##        self.redirect(token.generate_authorize_url())
        logging.info('how about here?')

        result = []
##        self.response.out.write(result)

class OAuthHandler(webapp.RequestHandler):
    def get(self):
        logging.info('Do you see this message?')

        url = atom.http_core.Uri.parse_uri(self.request.uri)
        if 'error' in url.query:
            pass
        else:
            token.get_access_token(url.query)

        self.response.out.write('asdfasdfasdfasdf')

application = webapp.WSGIApplication(
    [('/', MainHandler),
     ('/about', AboutHandler),
     ('/api', ApiHandler),
     ('oauth2callback', OAuthHandler)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
