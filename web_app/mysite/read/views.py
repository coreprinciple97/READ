from django.shortcuts import render, get_object_or_404, get_list_or_404
from django.http import HttpResponse, Http404, HttpResponseRedirect, FileResponse, JsonResponse
from django.urls import reverse
from .forms import LoginForm, RegistrationForm, AddClassroomForm, AddDocumentForm, StudentUploadPhotoForm, GoogleForm
from .models import User, Student, Teacher, Classroom, Document, Enrolled_in, Student_Notice, Student_Document
from django.contrib.auth import authenticate, logout
from django.contrib.auth import login
from django import forms
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from datetime import datetime
from django.conf import settings
import os.path
from os import path
from . import face_authenticate
import json

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.views.decorators.csrf import csrf_exempt

from .serializers import DocumentSerializer, UserSerializer
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

# for creating token when user is created
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)

    for user in User.objects.all():
        Token.objects.get_or_create(user=user)
# ===============================================
# Miscellaneous functions
# ===============================================
def user_is_student(user):
    return user.is_student

def user_is_teacher(user):
    return user.is_teacher

def user_not_admin(user):
    return not user.is_superuser

def user_is_admin(user):
    return user.is_superuser

def student_enrolled_in_class(user, class_name):
    try:
        student = Student.objects.get(user=user)
    except:
        raise Exception('student not found')
    try:
        classroom = Classroom.objects.get(name=class_name)
    except:
        raise Exception('classroom not found')
    try:
        enrolled_in_class = Enrolled_in.objects.get(student=student, classroom=classroom)
        return enrolled_in_class.status
    except:
        return False
# ===============================================
# Common views
# ===============================================

def index(request):
    return HttpResponseRedirect(reverse('login_view'))

@login_required
@user_passes_test(user_is_admin)
def admin_redirected_view(request):
    # If user is already logged into the website as admin, other user types won't work.
    return HttpResponse('<h1>You are logged in as admin.<br>Logout as admin to log in as a regular user.</h1>')


@login_required
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def logged_in_view(request):
    # Redirect the user to the correct page depending on user type
    if(request.user.is_superuser):
        return HttpResponseRedirect(reverse('admin_redirected_view'))
    if(request.user.is_teacher):
        return HttpResponseRedirect(reverse('teacher_classes_view'))
    if(request.user.is_student):
        return HttpResponseRedirect(reverse('student_classes_view'))
    else:
        raise Exception('user is not teacher or student')

@login_required
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse('login_view'))


@csrf_exempt
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def google_sign_in_view(request):
    if(request.user.is_authenticated):
        return HttpResponseRedirect(reverse('logged_in_view'))
    if(request.method == 'POST'):
        email = request.POST.get('email')
        #redirection
        if(email is not None):
            if(User.objects.filter(email=email).exists()): # if the email exists then user is already registered
                user = User.objects.get(email=email)
                login(request, user)
                if('email' in request.session):
                    del request.session['email']
                return HttpResponseRedirect(reverse('logged_in_view'))
            else:
                # email doesn't exist. Ask the user for additional information that cannot be obtained from google accounts
                form = GoogleForm()
                request.session['email'] = email
        else:
            # form submission
            form = GoogleForm(request.POST)
            if(form.is_valid()):
                username = form.cleaned_data['username']
                type_of_user = form.cleaned_data['type_of_user']
                email = request.session['email']
                assert email is not None
                user = None
                # create new table entry depending on user type.
                # Since password is required by django's User class, set_unusable_password() is called to set a dummy password.
                # django provides this functions implementation
                if(type_of_user == 'student'):
                    user = User(username=username, email=email, is_student=True)
                    user.set_unusable_password()
                    student = Student(user=user)
                    user.save()
                    student.save()
                else:
                    assert type_of_user == 'teacher'
                    user = User(username=username, email=email, is_teacher=True)
                    user.set_unusable_password()
                    teacher = Teacher(user=user)
                    user.save()
                    teacher.save()
                login(request, user)
                del request.session['email']
                return HttpResponseRedirect(reverse('logged_in_view'))

            else:
                # form has errors
                pass

    else:
        # check the request dictionary to see if 'email' keyword is there
        # its presence indicates user has arrived from google-sign in
        if('email' not in request.session):
            return HttpResponseRedirect(reverse('login_view'))
        form = GoogleForm()
    return render(request, 'read/google_sign_in.html', {'form' : form})



@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def login_view(request):
    if(request.user.is_authenticated):
        return HttpResponseRedirect(reverse('logged_in_view'))
    error_message = None
    if(request.method == 'POST'):
        # post method indicates that user has submitted login data
        # populate the form with data in the request dictionary
        form = LoginForm(request.POST)
        # form.is_valid() performs validation checks on the data entered by the user
        if(form.is_valid()):
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(username=username, password=password)
            # some checks cannot be implemented in the form classes. So we do them here
            if(user is None):
                error_message = "Incorrect username or password."
            else:
                login(request, user)
                return HttpResponseRedirect(reverse('logged_in_view'))
    else:
        # get method indicates user needs to fill in data
        form = LoginForm()
    return render(request, 'read/login.html', {'form': form, 'error_message': error_message})

@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def register_view(request):
    if(request.user.is_authenticated):
        return HttpResponseRedirect(reverse('logged_in_view'))
    if(request.method == 'POST'):
        # fill up registration form with data from request dict
        form = RegistrationForm(request.POST)
        if(form.is_valid()):
            type_of_user = form.cleaned_data['type_of_user']
            user = form.save(commit=False)
            # similar to the previous view, we need to perform additional checks beyond those done in is_valid()
            if(type_of_user == 'student'):
                user.is_student = True # set the corresponding user boolean value
                user.set_password(user.password)
                student = Student(user=user)
                # the order of saving the entries is critical here
                # a student cannot be created without the corresponding user entry
                # so create user first
                user.save()
                student.save()
            else:
                assert type_of_user == 'teacher'
                user.is_teacher = True
                user.set_password(user.password)
                teacher = Teacher(user=user)
                user.save()
                teacher.save()

            return HttpResponseRedirect(reverse('login_view'))
    else:
        form = RegistrationForm()
    return render(request, 'read/register.html', {'form': form})


# ===============================================
# Teacher views
# ===============================================
@login_required
@user_passes_test(user_is_teacher)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def teacher_classes_view(request):
    action = request.POST.get('action')
    if(action == 'add_class'):
        # depending on the action value, we add or delete
        return HttpResponseRedirect(reverse('teacher_adds_classroom_view'))
    elif(action == 'delete'):
        class_name = request.POST.get('class_name')
        assert class_name is not None
        _class = Classroom.objects.get(name=class_name)
        _class.delete()
    else:
        assert action is None

    cur_teacher = Teacher.objects.get(user_id=request.user.id)
    try:
        # get a list of all the classes whose teacher id matches the id of the current teacher
        # Now we try to find out the number of pending requests for each class
        # By default the number of pending requests is zero
        # iterate over the classes and find the number of enrolled_in objects which have status set to false
        classes = Classroom.objects.filter(teacher_id=cur_teacher.user_id)
        pending_requests = [0 for x in range(classes.count())]
        for idx, _class in enumerate(classes):
            pending_requests[idx] = Enrolled_in.objects.filter(classroom=_class, status = False).count()
    except(Classroom.DoesNotExist):
        classes = None
        pending_requests = None

    return render(request, 'read/teacher/teacher_classes.html', {'classes' : classes, 'pending_requests' : pending_requests})



@login_required
@user_passes_test(user_is_teacher)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def teacher_adds_classroom_view(request):
    if(request.method == 'POST'):
        form = AddClassroomForm(request.POST)
        if(form.is_valid()):
            classroom = form.save(commit=False)
            classroom.teacher = Teacher(user=request.user)
            classroom.save()
            return HttpResponseRedirect(reverse('teacher_classes_view'))
    else:
        form = AddClassroomForm()
    return render(request, 'read/teacher/teacher_adds_classroom.html', {'form' : form})


@login_required
@user_passes_test(user_is_teacher)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def teacher_file_view(request, class_name, file_name):
    classroom = Classroom.objects.get(name=class_name)
    try:
        try:
            doc = Document.objects.get(classroom=classroom, name=file_name)
        except:
            raise Exception('Error retrieving file')
        path = settings.MEDIA_ROOT + str(doc.document_file)
        # a FileResponse directly renders the pdf file. THus we avoid having to render pdf files through iframes or other difficult means.
        return FileResponse(open(path, 'rb'), content_type='application/pdf')
    except FileNotFoundError:
        raise Http404('File does not exist')


@login_required
@user_passes_test(user_is_teacher)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def teacher_specific_class_view(request, class_name):
    # get_object_or_404() allows us to void try, catch blocks.
    cur_class = get_object_or_404(Classroom, name=class_name)
    if(request.method == 'POST'):
        action = request.POST.get('action')
        # the value of the action field indicates the... well... action
        if(action == "Add document"):
            return  HttpResponseRedirect(reverse('teacher_adds_document_view', kwargs={'class_name': class_name}))
        elif(action == "Delete Document"):
            doc_to_delete = request.POST.get('name')
            assert doc_to_delete is not None
            ret = Document.objects.get(classroom=cur_class, name=doc_to_delete).delete()
            # an object of type 'read.Document' is deleted
            assert ret[1]['read.Document'] == 1
        elif(action == 'Approve'):
            student_to_enroll = request.POST.get('student_name')
            assert student_to_enroll is not None
            student = Student.objects.get(user__username=student_to_enroll)
            enrolled_in_instance = Enrolled_in.objects.get(student=student, classroom=cur_class)
            assert enrolled_in_instance.status == False
            assert enrolled_in_instance is not None
            enrolled_in_instance.status = True
            enrolled_in_instance.save()
            # add a notice when a request is approved, denied. Or when a teacher removes a student.
            notice = Student_Notice(student=student, notice=f"Request to join {cur_class.name} has been approved")
            notice.save()
        elif(action == 'Decline'):
            student_to_decline = request.POST.get('student_name')
            student = Student.objects.get(user__username=student_to_decline)
            enrolled_in_instance = Enrolled_in.objects.get(student=student, classroom=cur_class)
            assert enrolled_in_instance is not None
            assert enrolled_in_instance.status == False
            enrolled_in_instance.delete()
            notice = Student_Notice(student=student, notice=f"Request to join {cur_class.name} has been denied")
            notice.save()
        elif(action == 'Remove Student'):
            student_name = request.POST.get('student_name')
            student = Student.objects.get(user__username=student_name)
            Enrolled_in.objects.get(classroom = cur_class, student=student).delete()
            notice = Student_Notice(student=student, notice=f"You have been removed from {cur_class.name}")
            notice.save()
        else:
            # if it gets here we raise an exception since 1==0 is always false
            assert 1 == 0

    try:
        # get a list of all the students enrolled in this class.
        enrolled_students_pks = Enrolled_in.objects.filter(classroom=cur_class, status=True).values_list('student', flat=True)
        enrolled_students = Student.objects.filter(pk__in=enrolled_students_pks)
    except:
        enrolled_students = None

    try:
        pending_requests = Enrolled_in.objects.filter(classroom=cur_class, status=False)
    except:
        pending_requests = None

    try:
        uploaded_documents = Document.objects.filter(classroom=cur_class)
    except(Document.DoesNotExist):
        uploaded_documents = None

    return render(request, 'read/teacher/teacher_specific_class.html', {'class' : cur_class, 'enrolled_students' : enrolled_students, 'uploaded_documents' : uploaded_documents, 'pending_requests' : pending_requests})

@login_required
@user_passes_test(user_is_teacher)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def teacher_stats_view(request, class_name):
    cur_class = get_object_or_404(Classroom, name=class_name)
    cur_class_enrolled_in = Enrolled_in.objects.filter(classroom = cur_class, status=True)
    cur_class_student_doc = Student_Document.objects.filter(enrolled_in__in=cur_class_enrolled_in)

    # for time-student graph
    student_usernames = []
    student_time_data = []
    for entry in cur_class_enrolled_in:
        username = entry.student.user.username
        student_usernames.append(username)

        # find the total amount of time spent on all documents by each student
        student_doc = Student_Document.objects.filter(enrolled_in=entry).aggregate(Sum('time_spent'))
        try:
            time = int(student_doc.get('time_spent__sum'))
        except:
            time = 0
        student_time_data.append(time)


    # javascript package chart.js requires data as JSON
    json_student_usernames = json.dumps(student_usernames)
    json_student_time_data = json.dumps(student_time_data)

    # for time-document graph
    document_names = []
    doc_time_data = []
    cur_class_docs = Document.objects.filter(classroom=cur_class)
    for doc in cur_class_docs:
        # find the total amount of time spent on each document by all students
        student_doc = Student_Document.objects.filter(enrolled_in__in=cur_class_enrolled_in, document=doc).aggregate(Sum('time_spent'))
        try:
            time = int(student_doc.get('time_spent__sum'))
        except:
            time = 0
        document_names.append(doc.name)
        doc_time_data.append(time)

    json_doc_names = json.dumps(document_names)
    json_doc_times = json.dumps(doc_time_data)

    return render(request, 'read/teacher/teacher_stats.html', {'student_time_data' : json_student_time_data, 'student_labels' : json_student_usernames, 'doc_time_data' : json_doc_times, 'doc_labels' : json_doc_names})


@login_required
@user_passes_test(user_is_teacher)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def teacher_adds_document_view(request, class_name):
    cur_class = Classroom.objects.get(name=class_name)
    if(request.method == 'POST'):
        form = AddDocumentForm(request.POST, request.FILES)
        if(form.is_valid()):
            document = form.save(commit=False)
            if(Document.objects.filter(name=document.name, classroom=cur_class).exists() == False):
                document.upload_date = datetime.today()
                document.classroom = cur_class
                document.save()
                return HttpResponseRedirect(reverse('teacher_specific_class_view', args=[class_name]))
            else:
                # don't allow duplicate names for documents within same class. Although documents can have same names, they must be in different classes
                form.add_error('name', 'Document with name already exists within this class')
    else:
        form = AddDocumentForm()
    return render(request, 'read/teacher/teacher_adds_document.html', {'form' : form, 'class_name' : class_name})

# ===============================================
# Student views
# ===============================================
@login_required
@user_passes_test(user_is_student)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def student_classes_view(request):
    student = Student(user=request.user)
    if(request.method == 'POST'):
        action = request.POST.get('action')
        if(action == 'Leave Class'):
            class_name = request.POST.get('class_name')
            _class = Classroom.objects.get(name=class_name)
            assert _class is not None
            enrolled_in_instance = Enrolled_in.objects.get(student=student, classroom=_class)
            enrolled_in_instance.delete()

    try:
        enrolled_classes_pks = Enrolled_in.objects.filter(student=student, status=True).values_list('classroom', flat=True)
        enrolled_classes = Classroom.objects.filter(pk__in=enrolled_classes_pks)
    except:
        enrolled_classes = None

    return render(request, 'read/student/student_classes.html', {'enrolled_classes' : enrolled_classes})

@login_required
@user_passes_test(user_is_student)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def student_join_class_view(request):
    student = Student(user = request.user)
    if(request.method == 'POST'):
        # post method means form was submitted
        # get the required values from the form submission
        action = request.POST.get('action')
        class_name = request.POST.get('class_name')
        classroom = Classroom.objects.get(name=class_name)
        assert class_name is not None
        assert action is not None
        # in this view the only possible action should be join class
        if(action == 'Join Class'):
            enrolled_in_instance = Enrolled_in(student=student, classroom=classroom, status=False)
            enrolled_in_instance.save()
        else:
            raise Exception('action error in student_join_class_view')



    try:
        # find the list of classes that the studnet is enrolled in
        joined_classes_pks = Enrolled_in.objects.filter(student=student, status=True).values_list('classroom', flat=True)
        joined_classes = Classroom.objects.filter(pk__in=joined_classes_pks)
    except:
        joined_classes = None

    try:
        # get a list of all classes and exclude those the studnet is in, to find the classes the studnet has not joined
        if(joined_classes is None):
            not_joined_classes = Classroom.objects.all()
        else:
            not_joined_classes = Classroom.objects.exclude(pk__in=joined_classes)


        # additional array to indicate enrollment status
        class_join_status = [0 for x in range(len(not_joined_classes))]
        for idx, _class in enumerate(not_joined_classes):
            try:
                status = Enrolled_in.objects.get(student=student, classroom=_class).status
                try:
                    assert status is False
                except:
                    raise Exception('Status should be false')
                status = 'Pending Approval'
            except:
                status = None
                status = 'Not joined'
            class_join_status[idx] = status



    except:
        not_joined_classes = None
        class_join_status = None

    return render(request, 'read/student/student_join_class.html', {'not_joined_classes' : not_joined_classes, 'class_join_status' : class_join_status})




@login_required
@user_passes_test(user_is_student)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def student_notices_view(request):
    student = Student.objects.get(user=request.user)
    if(request.method == 'POST'):
        # post means remove notice was clicked
        # so delete the notice entry
        notice_pk = int(request.POST.get('notice_pk'))
        assert notice_pk is not None
        notice = Student_Notice.objects.get(pk=notice_pk)
        notice.delete()


    try:
        notices = Student_Notice.objects.filter(student=student)
    except Exception as e:
        notices = None
    #reverse the list to have newest entry at the top
    reversed_notices = list(reversed(notices))

    return render(request, 'read/student/student_notices.html', {'notices' : reversed_notices})




@login_required
@user_passes_test(user_is_student)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def student_specific_class_view(request, class_name):
    request.session['facial_authentication_done'] = False
    if(student_enrolled_in_class(request.user, class_name) == False):
        return HttpResponseRedirect(reverse('student_classes_view'))
    classroom = Classroom.objects.get(name=class_name)
    try:
        # find a list of all the docs for this classroom
        docs = Document.objects.filter(classroom=classroom)
    except:
        docs = None

    return render(request, 'read/student/student_specific_class.html', {'class' : classroom, 'docs' : docs})


@login_required
@user_passes_test(user_is_student)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def student_authenticate_view(request, class_name, file_name):
    if(student_enrolled_in_class(request.user, class_name) == False):
        return HttpResponseRedirect(reverse('student_classes_view'))

    student = Student.objects.get(user=request.user)
    photo_not_uploaded = True
    try:
        photo_path = student.photo.path
        if(path.exists(photo_path) == False):
            photo_path = None
        else:
            photo_not_uploaded = False
    except:
        photo_path = None

    authenticated = False
    # if photo is not uploaded then we display a message asking to upload a photo
    # if photo is uploaded then the following block will run
    if(photo_not_uploaded == False):
        name = student.user.first_name + ' ' + student.user.last_name
        authenticate_result = face_authenticate.facial_recognition(name, photo_path)
        # the values of authenitcated_result are defined in face_authenticate.py
        # copied here for convinience:
        # (0 => match not found, 1 => match found, 2 => face not detected in profile photo, 3 => broken image)
        # authenticated variable is somewhat redundant but this seems cleaner

        authenticated = 0
        if(authenticate_result == 0):
            authenticated = 0
        elif(authenticate_result == 1):
            authenticated = 1
            request.session['facial_authentication_done'] = True
            return HttpResponseRedirect(reverse('student_file_view', args=[class_name, file_name]))
        elif(authenticate_result == 2):
            authenticated = 2
        else:
            assert authenticate_result == 3
            authenticated = 3

    return render(request, 'read/student/student_authentication.html', {'photo_not_uploaded' : photo_not_uploaded, 'authenticated' : authenticated})


@login_required
@user_passes_test(user_is_student)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def student_file_view(request, class_name, file_name):
    # if someone tries to access this page by directly entering the URL
    # i.e. without having gone through facial recognition
    # then we redirect to the class view
    if(request.session.get('facial_authentication_done', False) == False and request.method != 'POST'):
        return HttpResponseRedirect(reverse('student_specific_class_view', args = [class_name]))

    classroom = Classroom.objects.get(name=class_name)
    if(request.method == 'POST'):
        time_spent_reading = int(float(request.POST.get('elapsedTime')))
        assert time_spent_reading is not None

        student = Student.objects.get(user=request.user)
        enrolled_in = Enrolled_in.objects.get(student=student, classroom=classroom)
        assert enrolled_in.status == True
        doc = Document.objects.get(classroom=classroom, name=file_name)
        try:
            # find the document entry and add to it the total time student spent reading it
            student_doc = Student_Document.objects.get(enrolled_in=enrolled_in, document=doc)
            student_doc.time_spent += time_spent_reading
            student_doc.save()
        except(Student_Document.DoesNotExist):
            # if this is the first time student opened this document, we create a new entry
            student_doc = Student_Document(enrolled_in=enrolled_in, document=doc, time_spent=time_spent_reading)
            student_doc.save()

        notice = Student_Notice(student=student, notice=f"You spent {time_spent_reading} seconds on the document: {doc.name}")
        notice.save()

        request.session['facial_authentication_done'] = False
        return HttpResponseRedirect(reverse('student_specific_class_view', args=[class_name]))

    if(student_enrolled_in_class(request.user, class_name) == False):
        request.session['facial_authentication_done'] = False
        return HttpResponseRedirect(reverse('student_classes_view'))

    try:
        try:
            doc = Document.objects.get(classroom=classroom, name=file_name)
        except:
            raise Exception('Error retrieving file')
        path = settings.MEDIA_URL + str(doc.document_file)
    except FileNotFoundError:
        raise Http404('File does not exist')

    return render(request, 'read/student/student_file.html', {'path' : path, 'class_name' : class_name, 'file_name' : file_name})

@login_required
@user_passes_test(user_is_student)
@user_passes_test(user_not_admin, login_url='/read/admin_redirected')
def student_photo_view(request):
    student = Student.objects.get(user=request.user)
    # if student submits a new photo or wants to remove current photo
    if(request.method == 'POST'):
        action = request.POST.get('action')
        if(action == 'Submit'):
            form = StudentUploadPhotoForm(request.POST, request.FILES)
            if(form.is_valid()):
                cur_student = form.save(commit=False)
                student.photo = cur_student.photo
                student.save()
        else:
            assert action == 'Remove Photo'
            form = StudentUploadPhotoForm()
            student.photo = None
            student.save()
    else:
        form = StudentUploadPhotoForm()

    try:
        photo_url = student.photo.url
        photo_path = student.photo.path
        if(path.exists(photo_path) == False):
            photo_url = None
    except:
        photo_url = None

    return render(request, 'read/student/student_photo.html', {'form' : form, 'photo_url' : photo_url})

