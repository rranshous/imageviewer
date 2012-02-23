
import web
import os

from lib.discovery import connect
from lib.images import Images, o as io
from lib.revent import ReventClient

import redis
import urlparse

import logging
import logging.config
here = os.path.dirname(os.path.abspath(__file__))
logging_conf = os.path.join(here,'logging.conf')
logging.config.fileConfig(logging_conf)
log = logging.getLogger('server')

redis_host = '127.0.0.1'

# our redis client for setting / getting info
rc = redis.Redis(redis_host)

# we are adding in the revent system for broadcasting
# events, we are going to pick a unique
revent = ReventClient(redis_host=redis_host)

## we are going to need to:
# track unique user's last viewed image id
# return back to the browser the url's for the next set of images
# keep track of user favorites
# keep track of user dislikes

# what name space are we using for our redis keys?
NS = 'ImageViewer'

class ImageDetails:

    def POST(self):
        """
        allows setting user's classification for images
        """

        # get our post data
        #data = urlparse.parse_qs(web.data())
        data = web.input()

        # make sure we have what we need
        if not data.get('user_id_string'):
            log.warning('ImageDetails POST: no user id')
            web.badrequest()
        if not data.get('image_id'):
            log.warning('ImageDetails POST: no image id')
            web.badrequest()
        if not data.get('level'):
            log.warning('ImageDetails POST: no level')
            web.badrequest()

        try:
            user_id_string = data.get('user_id_string')
            image_id = int(data.get('image_id'))
            level = float(data.get('level'))
        except ValueError, ex:
            log.exception('Could not cast as int')
            web.badrequest()

        # time to vote
        key = '%s:user_classifications:%s' % (NS, user_id_string)

        log.debug('setting user classification into key [%s] %s %s',
                  key, image_id, level)

        # votes are kept in sorted sets, one set per user
        # the weight will be the lvl
        rc.zadd(key, image_id, level)

        # let the world know what we think
        try:
            revent.fire('imageviewer.user_classification', {
                        'user_id_string':user_id_string,
                        'image_id':image_id,
                        'level':level})
        except Exception, ex:
            log.exception('Trying to fire imageviewer.user_classification' + \
                          ' user_id=%s, image_id=%s, level=%s' % (user_id_string,
                                                                  image_id,
                                                                  level))

        # success !
        return '1'

    def GET(self,user_id_string):
        """
        return back the info for the next set of images
        expects to receive the user id string
        can receive the id of the last viewed image
        """

        # make sure we have a user string
        if not user_id_string:
            log.warning('ImageDetails GET [%s]: no user id string' %
                        user_id_string)
            web.badrequest()

        # find user's last viewed
        key = '%s:user_details:%s' % (NS, user_id_string)
        last_viewed_id = rc.hget(key, 'last_viewed_id')
        if last_viewed_id:
            # we get back a string
            last_viewed_id = int(last_viewed_id)

        # if there is no last viewed, it's 0
        else:
            last_viewed_id = 0

        # find the data on the next set of images
        try:
            with connect(Images) as c:
                images = c.get_images_since(image_id=last_viewed_id,
                                            timestamp=None,
                                            limit=10,
                                            offset=0)
        except io.Exception, ex:
            log.exception('ImageDetails GET [%s] [%s]: getting images' %
                          (user_id_string,last_viewed_id))
            web.internalerror()

        # return back the id's of those images
        s = ','.join([str(i.id) for i in images])
        log.debug('returning images: %s' % s)

        # setup the header to be strait up text
        web.header('Content-type','text')

        return s


class ImageData:
    def GET(self, user_id_string, image_id):
        """
        return back given image's data
        expects the user id string, image id
        """

        log.debug('getting image data: %s %s', user_id_string, image_id)

        # make sure we have a user string
        if not user_id_string:
            log.warning('ImageData GET [%s] [%s]: no user id string' %
                        (user_id_string,image_id))
            web.notfound() # return error

        # make sure we have an image id
        if not image_id:
            log.warning('ImageData GET [%s] [%s]: no image id string' %
                        (user_id_string,image_id))
            web.notfound() # return error

        try:
            image_id = int(image_id)
        except ValueError, ex:
            log.warning('ImageData GET Error casting user id as int: %s',
                        image_id)

        # get the image details
        try:
            log.debug('ImageData GET ing data: %s', image_id)
            with connect(Images) as c:
                image = c.get_image(image_id)

        except io.Exception, ex:
            log.exception('ImageDetails GET [%s] [%s]: getting image' %
                          (user_id_string,image_id))
            web.internalerror() # return error

        if not image:
            web.notfound() # return error

        # update the users's last viewed image to this one
        key = '%s:user_details:%s' % (NS, user_id_string)
        rc.hset(key, 'last_viewed_id', image_id)

        # broadcast what we're looking at
        try:
            revent.fire('imageviewer.image_data', {
                        'user_id_string':user_id_string,
                        'image_id':image_id})

        except Exception, ex:
            log.exception('Trying to fire imageviewer.user_classification' + \
                          ' user_id=%s, image_id=%s, level=%s' % (user_id_string,
                                                                  image_id,
                                                                  level))

        # return back the image data
        return image.data



# setup our web.py urls
urls = (
    '/data/(.+?)/(.+?)/*', 'ImageData',
    '/details/(.+)/*', 'ImageDetails',
    '/details/', 'ImageDetails' # post rating
)
application = web.application(urls, globals())

if __name__ == "__main__":
    application.run()
