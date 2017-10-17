import random
from utility import parse_str_date, unix_to_real_time


class PageEntity(object):
    def __init__(self, page_id, page_name):
        self.page_id = page_id
        self.page_name = page_name


class Post(object):
    @staticmethod
    def get_target_fields(publish_status):
        base_field = "created_time,message"
        if publish_status == "published":
            base_field += ",promotion_status"
        if publish_status == "scheduled":
            base_field += ",scheduled_publish_time"
        return base_field

    def __init__(self, page_post_id, created_time, message):
        self.page_post_id = page_post_id
        self.created_time = parse_str_date(created_time)
        self.message = message

    @staticmethod
    def parse_post_from_json(json_data, publish_status):
        post_list = list([])
        if json_data:
            for post_obj in json_data:
                if "message" in post_obj:
                    page_post_id = post_obj['id']
                    created_time = post_obj['created_time']
                    message = post_obj['message']
                    if publish_status == "published":
                        promotion_status = str(post_obj.get("promotion_status", "")).title()
                        post = PostPublished(page_post_id, created_time, message, promotion_status)
                    elif publish_status == "scheduled":
                        if "scheduled_publish_time" not in post_obj:
                            continue
                        scheduled_publish_time = post_obj['scheduled_publish_time']
                        scheduled_time = unix_to_real_time(int(scheduled_publish_time))
                        post = PostScheduled(page_post_id, created_time, message, scheduled_time)
                    else:
                        post = PostUnpublished(page_post_id, created_time, message)
                    post_list.append(post)
        return post_list


class PostPublished(Post):
    def __init__(self, page_post_id, created_time, message, promotion_status):
        Post.__init__(self, page_post_id, created_time, message)
        self.promotion_status = promotion_status
        self.num_of_view = -1


class PostUnpublished(Post):
    def __init__(self, page_post_id, created_time, message):
        Post.__init__(self, page_post_id, created_time, message)


class PostScheduled(Post):
    def __init__(self, page_post_id, created_time, message, scheduled_time):
        Post.__init__(self, page_post_id, created_time, message)
        self.scheduled_time = scheduled_time
