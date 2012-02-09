

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
        data = web.data()

        # make sure we have what we need
        if not data.get('user_id'):
            web.badrequest()
        if not data.get('image_id'):
            web.badrequest()
        if not data.get('level'):
            web.badrequest()

        # time to vote
        key = '%s:user_classifications:%s' % (NS, data.get('user_id'))

        # votes are kept in sorted sets, one set per user
        # the weight will be the lvl
        rc.zadd(key,data.get('level'),data.get('image_id'))

        # success !
        return '1'

    def GET(self,user_id_string,last_viewed_id=None):
        """
        return back the info for the next set of images
        expects to receive the user id string
        can receive the id of the last viewed image
        """

        # make sure we have a user string
        if not user_id_string:
            log.warning('ImageDetails GET [%s] [%s]: no user id string' %
                        (user_id_string,last_viewed_id))
            web.badrequest()

        # if they didn't provide the last viewed image find it
        if not last_viewed_id:
            key = '%s:user_details:%s' % (NS, user_id_string)
            last_viewed_id = rc.hget(key, 'last_viewed_id')
            if last_viewed_id:
                last_viewed_id = int(last_viewed_id)

        # if there is no last viewed, it's 0
        if not last_viewed_id:
            last_viewed_id = 0
        else:
            # comes in from params / redis as string
            last_viewed_id = int(last_viewed_id)

        # find the data on the next set of images
        try:
            with connect(Image) as c:
                images = c.get_images_since(image_id=last_viewed_id,
                                            timestamp=None,
                                            limit=10,
                                            offset=0)
        except io.Exception, ex:
            log.exception('ImageDetails GET [%s] [%s]: getting images' %
                          (user_id_string,last_viewed_id))
            web.internalerror()

        # return back the id's of those images
        return ','.join([i.id for i in images])


class ImageData:
    def GET(self, user_id_string, image_id):
        """
        return back given image's data
        expects the user id string, image id
        """

        # make sure we have a user string
        if not user_id_string:
            log.warning('ImageData GET [%s] [%s]: no user id string' %
                        (user_id_string,image_id))
            web.notfound() # return error

        # get the image details
        try:
            with connect(Image) as c:
                image = c.get_image(image_id)

        except io.Exception, ex:
            log.exception('ImageDetails GET [%s] [%s]: getting image' %
                          (user_id_string,image_id))
            web.internalerror() # return error

        if not image:
            web.notfound() # return error

        # update the users's last viewed image to this one
        key = '%s:user_details:%s' % (NS, user_id_string)
        last_viewed_id = rc.hincr(key,'last_viewed_id',1)

        # return back the image data
        return image.data

