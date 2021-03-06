from flask import Flask, render_template, request, redirect, url_for, send_file
from backend.client import PagePostClient
from backend.utility import get_min_schedule_date, unix_to_real_time, Email, get_current_datetime
from backend.entity import PostPublished
from backend.config import email_api_key
import time, facebook, os

app = Flask(__name__)
page_client = PagePostClient()


def handle_error(error_message):
    # if an error happens and it is about active access token, redirect to login
    # otherwise return to failure.html and print the error message
    error_message = str(error_message)
    if error_message.find("access") >= 0 and error_message.find("token") >= 0:
        return redirect(url_for("login", login_message="Access token invalid now, please re-enter."))
    return render_template("failure.html", error_message=error_message)


@app.route('/')
@app.route('/login')
def login():
    login_message = request.args.get("login_message", "Please input your page access token")
    return render_template("login.html", login_message=login_message)


@app.route('/', methods=['POST'])
@app.route('/login', methods=['POST'])
def auth():
    access_token = request.form.get("access_token")
    try:
        page_client.update_token(access_token)
        return redirect("/home")
    except facebook.GraphAPIError as e:
        return handle_error(e.message)


@app.route('/home')
def home_dashboard():
    try:
        published_count = len(page_client.list_post("published"))
        unpublished_count = len(page_client.list_post("unpublished"))
        scheduled_count = len(page_client.list_post("scheduled"))
        page_client.get_page_insights()
        return render_template("home.html",
                               published_count=published_count,
                               unpublished_count=unpublished_count,
                               scheduled_count=scheduled_count,
                               page_name=page_client.page.page_name,
                               page=page_client.page)
    except facebook.GraphAPIError as e:
        return handle_error(e.message)


@app.route('/list_posts', methods=['GET'])
def list_posts():
    try:
        published_status = str(request.args.get("published_status", "published")).lower()
        post_list = page_client.list_post(published_status)
        follow_message = request.args.get("follow_message")
        if not follow_message:
            follow_message = "%s posts for page %s" % (published_status.title(), page_client.page.page_name)
        most_recent_scheduled_time = 0
        if published_status == "scheduled":
            most_recent_scheduled_time = page_client.get_earliest_scheduled_time()
        return render_template("list_posts.html", post_list=post_list,
                               most_recent_scheduled_time=most_recent_scheduled_time,
                               follow_message=follow_message, published_status=published_status)
    except facebook.GraphAPIError as e:
        return handle_error(e.message)


@app.route('/list_posts', methods=['POST'])
def view_post():
    try:
        if "view" in request.form:
            post_id = request.form.get("view")
            published_status = request.args.get("published_status")
            return redirect(url_for('view_post_details', post_id=post_id, published_status=published_status))
        elif "view_insights" in request.form:
            return redirect(url_for("get_post_insights"))
    except facebook.GraphAPIError as e:
        return handle_error(e.message)


@app.route('/view_post', methods=['GET'])
def view_post_details():
    try:
        post_id = request.args.get("post_id")
        published_status = request.args.get("published_status", "unpublished")
        post = page_client.get_target_post(post_id, published_status)
        if post:
            view_message = "not published/scheduled yet"
            if published_status == "published":
                view_message = "already published"
            elif published_status == "scheduled":
                view_message = "scheduled on %s" % post.scheduled_time
            return render_template("view_post.html", post=post,
                                   published_status=published_status, view_message=view_message)
        else:
            return handle_error(error_message="This post does not exist!")
    except facebook.GraphAPIError as e:
        return handle_error(e.message)


@app.route('/view_post', methods=['POST'])
def update_post():
    try:
        current_status = request.form.get("current_status")
        updated_status = request.form.get("updated_status")
        if 'edit' in request.form:
            # If the post is already published, cannot change it to unpublished or scheduled anymore.
            if "post_id" not in request.form:
                raise facebook.GraphAPIError("Not valid post ID to be updated.")
            response = page_client.update_post(message=request.form.get("message"),
                                               post_id=request.form.get("post_id"),
                                               current_status=current_status,
                                               updated_status=request.form.get("updated_status"),
                                               scheduled_time=request.form.get("scheduled_time"))
            if response is True:
                follow_message = "Successfully updated the post."
                return redirect(url_for('list_posts', published_status=updated_status, follow_message=follow_message))
            else:
                return handle_error(error_message=response)
        elif 'delete' in request.form:
            post_id = request.form.get("post_id")
            if page_client.delete_post(post_id):
                follow_message = "Successfully deleted the post"
                return redirect(url_for('list_posts', follow_message=follow_message, published_status=current_status))
            else:
                return handle_error(error_message="Failed to delete post %s " % post_id)
    except facebook.GraphAPIError as e:
        return handle_error(e.message)


@app.route('/new_post')
def draft_post():
    return render_template("new_post.html", current_date_time=get_min_schedule_date())


@app.route('/new_post', methods=["POST"])
def create_new_post():
    # create a new post based on the published status and scheduled time
    # if successfully created, go to the corresponding list_posts page
    parameters = dict(message=request.form.get("message"))
    # default as unpublished
    parameters["published_status"] = published_status = request.form.get("published_status", "unpublished")
    parameters["targeting"] = request.form.get("targeting_countries")
    if published_status == "scheduled" and "scheduled_time" in request.form:
        parameters["scheduled_time"] = request.form.get("scheduled_time")
    try:
        response = page_client.create_post(**parameters)
        if response is True:
            follow_message = "Successfully created a %s post on %s" % (published_status, unix_to_real_time(int(time.time())))
            return redirect(url_for('list_posts', published_status=published_status, follow_message=follow_message))
        return handle_error(error_message=response)
    except facebook.GraphAPIError as e:
        return handle_error(error_message=e.message)


@app.route('/post_insights', methods=["GET"])
def get_post_insights():
    try:
        post_list = page_client.get_post_insights_batch()
        follow_message = request.args.get("follow_message", "")
        return render_template("post_insights.html", post_list=post_list, follow_message=follow_message)
    except facebook.GraphAPIError as e:
        return handle_error(e.message)


@app.route('/post_insights', methods=["POST"])
def export_insights_csv():
    try:
        if "view" in request.form:
            post_id = request.form.get("view")
            return redirect(url_for("view_post_details", post_id=post_id, published_status="published"))
        elif "export_excel" or "send_email" in request.form:
            # convert post insights to csv objects
            file_name = "%s.xlsx" % get_current_datetime()
            excel_file_path = "%s/tmp/%s" % (os.path.dirname(os.path.abspath(__file__)), file_name)
            post_list = page_client.list_post("published")
            PostPublished.save_to_excel_file(excel_file_path, post_list)
            if "send_email" in request.form and "email_address" in request.form:
                email_address = request.form.get("email_address")
                subject = "Post insights from Kun's demo, %s" % file_name
                email = Email(email_api_key, email_to=email_address, subject=subject)
                email.add_text("Please see attachment")
                email.add_attachment(excel_file_path)
                if email.send():
                    follow_message = "Successfully sent email to %s" % email_address
                    return redirect(url_for("get_post_insights", follow_message=follow_message))
                return handle_error(error_message="Failed to send email to %s" % email_address)
            else:
                return send_file(excel_file_path, as_attachment=True)
    except facebook.GraphAPIError as e:
        return handle_error(e.message)


if __name__ == '__main__':
    app.run(host='localhost', port=4000, debug=True)
