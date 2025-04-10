import pkg_resources
import json
import logging
import os

from xblock.core import XBlock
from xblock.fields import Scope, Dict, String

from xblock.completable import CompletableXBlockMixin
from xblock.exceptions import JsonHandlerError
from xblock.fields import (
    UNIQUE_ID,
    Boolean,
    DateTime,
    Dict,
    Float,
    Integer,
    Scope,
    String,
)

from enum import Enum
from web_fragments.fragment import Fragment
from webob import Response

import datetime
from pytz import UTC
import requests

from django.conf import settings
from django.utils import timezone

try:
    from xblock.utils.resources import ResourceLoader
except (
    ModuleNotFoundError
):  # For backward compatibility with releases older than Quince.
    from xblockutils.resources import ResourceLoader
try:
    import importlib_resources
except ModuleNotFoundError:
    from importlib import resources as importlib_resources
    
from simulationxblock.utils import (
    get_simulation_storage,
    str2bool,
    upload_on_cloud,
    read_file_from_s3,
)

# Make '_' a no-op so we can scrape strings
_ = lambda text: text

log = logging.getLogger(__name__)
loader = ResourceLoader(__name__)

AWS_ACCESS_KEY_ID = ""
AWS_SECRET_ACCESS_KEY = ""
AWS_STORAGE_BUCKET_NAME = ""
AWS_REGION = "ap-southeast-1"
AWS_S3_CUSTOM_DOMAIN = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com"

SIMULATIONXBLOCK_ROOT = os.path.join(settings.MEDIA_ROOT, "icdl")
SIMULATIONXBLOCK_URL = os.path.join(settings.MEDIA_URL, "icdl")
SIMULATIONXBLOCK_STORAGE = get_simulation_storage()

class SubmissionStatus(Enum):
    """Submission options for the assignment."""

    NOT_ATTEMPTED = _("Not attempted")
    COMPLETED = _("Completed")


@XBlock.wants("user")
@XBlock.wants("i18n")
class OfficeQuestionBankXBlock(XBlock, CompletableXBlockMixin):
    # XBlock for managing a configurable Question Bank.
    display_name = String(
        display_name=_("Display Name"),
        default="Office Question Bank",
        scope=Scope.settings,
        help="The display name of the XBlock.",
    )

    has_score = Boolean(
        display_name=_("Is Scorable"),
        help=_("Select True if this component will save score"),
        default=True,
        scope=Scope.settings,
    )

    state_definitions = String(
        display_name=_("Question Bank"),
        default="[]",
        scope=Scope.content,
        help="The question bank configured by admin. This should be the valid JSON string content",
    )

    weight = Float(
        display_name=_("Problem Weight"),
        help=_(
            "Defines the number of points this problem is worth. If "
            "the value is not set, the problem is worth one point."
        ),
        values={"min": 0, "step": 0.1},
        scope=Scope.settings,
        default=1.0,
    )

    points = Integer(
        display_name=_("Maximum score"),
        help=_("Maximum grade score given to assignment by staff."),
        default=1,
        scope=Scope.settings,
    )

    weighted_score = Float(
        display_name=_("Problem weighted score"),
        help=_(
            "Defines the weighted score of this problem. If "
            "the value is not set, the problem is worth one point."
        ),
        scope=Scope.user_state,
        default=0,
    )

    submission_status = String(
        display_name=_("Submission status"),
        help=_("The submission status of the assignment."),
        default=SubmissionStatus.NOT_ATTEMPTED.value,
        scope=Scope.user_state,
    )
    
    simulation_content_json_path = String(
        display_name=_("Upload Simulation content"),
        help=_("Upload Simulation content"),
        scope=Scope.settings,
    )
    
    simulation_content_meta = Dict(scope=Scope.content)
    
    # def resource_string(self, path):
    #     # Helper to load resources
    #     return pkg_resources.resource_string(__name__, path).decode("utf-8")

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        try:
            data = importlib_resources.files(__name__).joinpath(path).read_bytes()
        except TypeError:
            data = importlib_resources.files(__package__).joinpath(path).read_bytes()
        return data.decode("utf8")

    def render_template(self, template_path, context):
        """
        Render a template with the given context. The template is translated
        according to the user's language.

        Args:
            template_path (str): The path to the template
            context(dict, optional): The context to render in the template

        Returns:
            str: The rendered template
        """
        return loader.render_django_template(
            template_path,
            context,
            i18n_service=self.runtime.service(self, "i18n"),
        )

    def student_view(self, request, context=None):
        # path = self._get_full_path()
        path = ""
        user_service = self.runtime.service(self, "user")
        user = user_service.get_current_user()
        xblock_id = str(self.location.block_id)
        block_locator = str(self.location)
        # base_url = request.build_absolute_uri('/')
        # xblock_url = f"{base_url}xblock/{self.location.block_id}/"
        context = {
            "simulation_xblock": self,
            "xblock_id": xblock_id,
            # "xblock_url" : xblock_url,
            "block_locator": block_locator,
            "path": path,
        }
        
        state_definitions_str = self.get_state_definitions()

        # case init data
        if len(state_definitions_str) == 0:
            state_definitions_str = '[]'

        # validation is_json and object have property
        state_definitions = json.loads(state_definitions_str)

        json_args = {
            "user_email": user.emails[0],
            "state_definitions": state_definitions_str,
            "simulationJsonPath": self.simulation_content_json_path
        }

        if len(state_definitions) > 0:
            if "application" in state_definitions[0]:
                json_args["app"] = state_definitions[0]["application"]

            if "template" in state_definitions[0]:
                json_args["template"] = state_definitions[0]["template"]

            if "trackingOnlyApp" in state_definitions[0]:
                json_args["tracking_only_app"] = state_definitions[0]["trackingOnlyApp"]
                
            if "trackingOnlyCOM" in state_definitions[0]:
                json_args["tracking_only_com"] = state_definitions[0]["trackingOnlyCOM"]
            
        # The view shown to students
        template = self.render_template("static/html/student_view.html", context)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/style.css"))
        # frag.add_javascript(self.resource_string("static/dist-fe/index.js"))
        frag.add_javascript(self.resource_string("static/js/installRequired.js"))
        frag.add_javascript(self.resource_string("static/js/student_view.js"))
        frag.initialize_js(
            "OfficeQuestionBankXBlockStudent",
            json_args = json_args,
        )
        return frag
    
    def get_state_definitions(self):
        if len(self.simulation_content_json_path) > 0:
            log.info(AWS_S3_CUSTOM_DOMAIN)
            json_path = self.simulation_content_json_path
            if json_path.startswith("https:") or json_path.startswith("http:"):
                json_path = json_path.replace(AWS_S3_CUSTOM_DOMAIN + "/", "")
                log.info("json_path: %s", json_path)
            
            log.info(json_path)
            
            file_content = read_file_from_s3(AWS_STORAGE_BUCKET_NAME, json_path)
            if len(file_content) > 0:
                log.info("get value s3 for self.state_definitions: %s", file_content)
                return file_content
            
        return self.state_definitions

    def str2bool(self, val):
        """Converts string value to boolean"""
        return val in ["True", "true", "1"]

    def is_json(self, json_obj):
        if isinstance(json_obj, (dict, list)):  # Nếu đã là object JSON hợp lệ
            return True
        if isinstance(json_obj, str):  # Nếu là chuỗi, thử parse nó
            try:
                json.loads(json_obj)
                return True
            except ValueError:  # Không phải JSON hợp lệ
                return False
        return False  # Không phải JSON hợp lệ

    
    @property
    def store_content_on_local_fs(self):
        return SIMULATIONXBLOCK_STORAGE.__class__.__name__ == 'FileSystemStorage'

    @property
    def get_block_path_prefix(self):
        # return ""
        # In worbench self.location is a mock object so we have to use usage_id
        if 'Workbench' in self.runtime.__class__.__name__:
            return str(self.scope_ids.usage_id)
        else:
            return os.path.join(self.location.org, self.location.course, self.location.block_id)

    @property
    def simulation_content_url(self):
        return "{}/{}".format(SIMULATIONXBLOCK_URL, self.get_block_path_prefix)

    @property
    def local_storage_path(self):
        return os.path.join(
            SIMULATIONXBLOCK_ROOT, self.get_block_path_prefix
        )

    @property
    def cloud_storage_path(self):
        return os.path.join(
            'icdl', self.get_block_path_prefix
        )

    def get_context_studio(self):
        return {
            "field_display_name": self.fields["display_name"],
            "is_scorable": self.fields["has_score"],
            "weight": self.fields["weight"],
            "points": self.fields["points"],
            "state_definitions": self.fields["state_definitions"],
            "simulation_content_json_path": self.fields["simulation_content_json_path"],
            "simulation_xblock": self,
        }

    def studio_view(self, context=None):
        context = self.get_context_studio()
        log.info(context)
        template = self.render_template("static/html/admin_view.html", context)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/style.css"))
        frag.add_javascript(self.resource_string("static/js/admin_view.js"))
        frag.initialize_js("OfficeQuestionBankXBlockAdmin")
        return frag

    @XBlock.handler
    def user_interaction_data(self, request, suffix=""):
        """
        Handles to retrieve and save user interactions with simulation content
        """
        success = False
        if request.method == "POST":
            try:
                # self.interaction_data = request.POST['data']
                success = True
            except BaseException as exp:
                log.error("Error while saving learner interaction data: %s", exp)

        # return Response(json.dumps(request.POST['data']))
        return Response(json.dumps({"success": success}))

    @staticmethod
    def validate_score(points: int, weight: int) -> None:
        """
        Validate a score.

        Args:
            score (int): The score to validate.
            max_score (int): The maximum score.
        """
        try:
            points = int(points)
        except ValueError as exc:
            raise JsonHandlerError(400, "Points must be an integer") from exc

        if points < 0:
            raise JsonHandlerError(400, "Points must be a positive integer")

        weight = weight.replace(",", ".")

        if weight:
            try:
                weight = float(weight)
            except ValueError as exc:
                raise JsonHandlerError(400, "Weight must be a decimal number") from exc
            if weight < 0:
                raise JsonHandlerError(400, "Weight must be a positive decimal number")

        return points, weight

    # @XBlock.json_handler
    @XBlock.handler
    def result_handler(self, request, suffix=""):
        """
        Handler to injest results when simulationxblock content triggers completion or rescorable events
        """
        # log.info(request)
        raw_body = request.body.decode('utf-8')

        # try parse JSON from body
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            return Response(json.dumps({"error": "Invalid JSON"}), content_type="application/json", status=400)
        
        # Grade
        # state_definitions = json.loads(self.state_definitions)
        state_definitions = json.loads(self.get_state_definitions())
        stateExpected = state_definitions[0]["criteria"]["stateExpected"]
        keys_to_compare = list(stateExpected.keys())
        finalState = data["finalState"]

        differences = {}
        if "finalState" in data:
            for key in keys_to_compare:
                valFinalState = finalState[key] if key in finalState else ""
                # if (type(valFinalState) == str and type(stateExpected[key]) == str) or (
                #     type(valFinalState) == bool and type(stateExpected[key]) == bool
                # ):
                if (type(stateExpected[key]) == str) or (
                    type(stateExpected[key]) == bool
                ):
                    if stateExpected[key] != valFinalState:
                        differences[key] = (stateExpected[key], valFinalState)

                else:
                    if (
                        type(stateExpected[key]) == dict
                        and "action" in stateExpected[key]
                    ):
                        log.info("key: %s , val: %s", key, valFinalState)
                        try:
                            result = self.word_compare_texts()
                            print(result)
                        except BaseException as exp:
                            log.error("Error while marking completion %s", exp)
                        except AttributeError:
                            print("Function does not exist.")

                log.info("key: %s , val: %s", key, valFinalState)
                log.info("type: %s", type(valFinalState))
                log.info("type: %s", type(stateExpected[key]))

            # differences = {key: (stateExpected[key], finalState[key]) for key in keys_to_compare if stateExpected[key] != finalState[key]}

        summary = {
            "wrong": len(differences),
            "correct": len(stateExpected) - len(differences),
            "total": len(stateExpected),
        }

        save_completion, save_score = False, False
        try:
            self.emit_completion(1.0)
            save_completion = True
            self.submission_status = SubmissionStatus.COMPLETED.value
        except BaseException as exp:
            log.error("Error while marking completion %s", exp)

        # if self.is_past_due:
        #     return Response(
        #         json.dumps(
        #             {
        #                 "result": {
        #                     "save_completion": save_completion,
        #                     "save_score": save_score,
        #                 }
        #             }
        #         ),
        #         content_type="application/json",
        #         charset="utf8",
        #     )

        if self.has_score and summary and summary["total"] > 0:
            score = 0
            if summary:
                score = summary["correct"] / summary["total"] * self.points

            grade_dict = {
                "value": score,
                "max_value": self.points,
                "only_if_higher": None,
            }

            log.info(grade_dict)
            user_service = self.runtime.service(self, "user")
            user = user_service.get_current_user()
            user_id = user.opt_attrs["edx-platform.user_id"]
            log.info(user_id)

            # # Send data to ICDL
            # try:
            #     block_locator = str(self.location)
            #     weighted_earned = 1 if score > 0.5 else 0
            #     # course_id = self.runtime.service(self, 'user').course_id

            #     url = self.runtime.handler_url(self, 'result_handler')
            #     full_url = request.path
            #     log.info("url: %s", url)
            #     log.info("full_url: %s", full_url)
                
            #     # referer = request.META.get('HTTP_REFERER')
            #     referer_url = request.headers.get('Referer', 'No referer provided')
                
            #     log.info("referer: %s", referer_url)
            #     # Lấy thông tin user context nếu runtime hỗ trợ
            #     # user_id = getattr(self.runtime, 'user_id', None)
            #     # course_id = getattr(self.runtime, 'course_id', None)
            #     course_id = str(self.scope_ids.usage_id.context_key)
            #     # referer_url = getattr(self.runtime, "headers", {}).get("Referer", "")

            #     # log.info(referer_url)
            #     # log.info(course_id)
            #     # log.info(user_id)
            #     now_utc = datetime.datetime.now(UTC).isoformat()

            #     grade_to_icdl = {
            #         "username": "",
            #         "referer": referer_url,
            #         "event": {
            #             "user_id": user_id,
            #             "course_id": course_id,
            #             "problem_id": block_locator,
            #             "event_transaction_id": "",
            #             "event_transaction_type": "",
            #             "weighted_earned": weighted_earned,
            #             "weighted_possible": 1,
            #         },
            #         "time": now_utc,
            #         "event_type": "",
            #         "event_source": "server",
            #     }

            #     log.info(grade_to_icdl)
                
            #     endpointICDL = 'https://vmbweb.vmb.edu.vn/api/user_answer_event/'
            #     headers = {
            #         'Content-type': 'application/json',
            #     }
            #     log.info("Send grade to ICDL: %s", endpointICDL)
            #     # r = requests.request('POST', endpointICDL, data=grade_to_icdl, headers=headers)
            #     r = requests.post(endpointICDL, json=grade_to_icdl)
            #     try:
            #         r.raise_for_status()
            #         log.info("raise_for_status: %s", r.raise_for_status())
            #     except requests.exceptions.RequestException as e:
            #         log.exception("Received %s status code. Text: %s", r.status_code, r.text)
            #         # raise e
            #     except Exception as e:
            #         log.exception("Unexpected error: %s", e)
            #         # raise e
                    
            # except Exception as exp:
            #     log.exception("Unexpected error: %s", e)

            try:
                self.runtime.publish(self, "grade", grade_dict)

                self.runtime.publish(
                    self,
                    "grade",
                    {
                        "value": score,
                        "max_value": self.points,
                        "user_id": user_id,
                    },
                )

                save_score = True
                log.info("self.runtime.publish grade for simulator xblock")
            except TypeError:
                grade_dict["only_if_higher"] = False
                self.runtime.publish(self, "grade", grade_dict)
                save_score = True
            except BaseException as exp:
                log.error("Error while publishing score %s", exp)

            if save_score and score > self.weighted_score:
                self.weighted_score = score

        return Response(
            json.dumps(
                {
                    "result": {
                        "save_completion": save_completion,
                        "save_score": save_score,
                        "summary": summary,
                    }
                }
            ),
            content_type="application/json",
            charset="utf8",
        )

    @XBlock.handler
    def save_question_bank(self, request, suffix=""):
        if self.is_json(request.params["state_definitions"]) == False:
            return Response(
                json.dumps(
                    {"result": "error", "message": "state definition invalid json"}
                ),
                content_type="application/json",
                charset="utf8",
            )

        # log.info("is score %s", request.params["is_scorable"])
        self.display_name = request.params["display_name"]
        self.has_score = self.str2bool(request.params["is_scorable"])
        points = request.params["points"]
        weight = request.params["weight"]
        self.points, self.weight = self.validate_score(points, weight)
        self.state_definitions = request.params["state_definitions"]
        
        log.info(settings.AWS_S3_CUSTOM_DOMAIN)
        
        # upload file
        if hasattr(request.params["simulation_content_bundle"], "file"):
            json_file = request.params["simulation_content_bundle"].file  # InMemoryUploadedFile
            dataStateDefinitions = "[]"
            try:
                log.info("data %s", json_file)
                # Đọc nội dung JSON từ file đã upload
                dataStateDefinitions = json_file.read().decode("utf-8")  # Đọc file thành chuỗi
                
                if self.is_json(dataStateDefinitions) == False:
                    return Response(
                        json.dumps(
                            {"result": "error", "message": "state definition invalid json"}
                        ),
                        content_type="application/json",
                        charset="utf8",
                    )
                json_file.seek(0)  # Đưa con trỏ về đầu file
            except BaseException as exp:
                log.error("Error while marking completion %s", exp)
                return Response(
                    json.dumps(
                        {"result": "error", "message": "Invalid json"}
                    ),
                    content_type="application/json; charset=utf-8",
                    status=400
                )

            except json.JSONDecodeError:
                return Response(
                    json.dumps({"result": "error", "message": "Invalid JSON"}).encode("utf-8"),
                    content_type="application/json",
                    status=400
                )
            
            meta_data = {
                "name": json_file.name,
                "upload_time": timezone.now().strftime(DateTime.DATETIME_FORMAT),
                "size": json_file.size,
            }
            log.info(json_file)
            log.info(meta_data)
                
            self.simulation_content_meta = meta_data
            if self.store_content_on_local_fs:
                # unpack_package_local_path(h5p_package, self.local_storage_path)
                self.simulation_content_json_path = self.simulation_content_url
            else:
                result_upload = upload_on_cloud(
                    json_file, SIMULATIONXBLOCK_STORAGE, self.cloud_storage_path
                )
                if result_upload is None:
                    return Response(
                        json.dumps({"result": "error", "message": "Upload to S3 failed"}).encode("utf-8"),
                        content_type="application/json",
                        status=400
                    )
                
                # self.simulation_content_json_path = SIMULATIONXBLOCK_STORAGE.url(self.cloud_storage_path)
                self.simulation_content_json_path = result_upload
                
                # override
                self.state_definitions = dataStateDefinitions

        elif request.params["simulation_content_path"]:
            self.simulation_content_json_path = request.params["simulation_content_path"]
            json_path = self.simulation_content_json_path
            log.info(json_path.startswith("https:"))
            if json_path.startswith("https:") or json_path.startswith("http:"):
                log.info(AWS_S3_CUSTOM_DOMAIN)
                json_path = json_path.replace(AWS_S3_CUSTOM_DOMAIN + "/", "")
                
            log.info(json_path)
            
            file_content = read_file_from_s3(AWS_STORAGE_BUCKET_NAME, json_path)
            if len(file_content) > 0:
                log.info("override content from s3")
                # override
                self.state_definitions = file_content
        
        return Response(
            json.dumps({"result": "success"}),
            content_type="application/json",
            charset="utf8",
        )

    @XBlock.json_handler
    def get_question_bank(self, data, suffix=""):
        # Return the question bank
        return {"questions": "test"}
        # return {"questions": self.question_bank}

    @XBlock.json_handler
    def handle_question(self, data, suffix=""):
        # Handle student interactions and verify actions
        question_id = data.get("question_id")
        student_action = data.get("student_action")
        question = ""
        # question = self.question_bank.get(str(question_id))
        if not question:
            return {"success": False, "message": "Invalid question ID."}
        criteria = question.get("criteria", {})
        if criteria["action"] == "insert_text" and student_action == criteria["text"]:
            return {"success": True, "message": "Correct text inserted!"}
        elif (
            criteria["action"] == "format_text" and student_action == criteria["style"]
        ):
            return {"success": True, "message": "Correct formatting applied!"}
        elif (
            criteria["action"] == "format_cell" and student_action == criteria["format"]
        ):
            return {"success": True, "message": "Correct cell format!"}
        else:
            return {"success": False, "message": "Action does not meet criteria."}

    @property
    def is_past_due(self):
        """
        Return True if the due date has passed.
        """
        if not self.due:
            return False
        return datetime.now() > self.due

    def word_compare_texts(self):
        return ""

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            (
                "OfficeQuestionBankXBlock",
                """<simulationxblock/>
             """,
            ),
            (
                "Multiple OfficeQuestionBankXBlock",
                """<vertical_demo>
                <simulationxblock/>
                <simulationxblock/>
                <simulationxblock/>
                </vertical_demo>
             """,
            ),
        ]
