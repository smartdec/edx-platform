# -*- coding: utf-8 -*-
"""
Command to generate statistics.
"""
import csv
import time
from time import sleep
import sys

from django.core.management.base import BaseCommand
from optparse import make_option

from xmodule.modulestore.django import modulestore
from courseware.courses import get_course
from django.contrib.auth.models import User

from instructor.offline_gradecalc import student_grades
from courseware import grades




class Command(BaseCommand):
    """
    Command to manually regenerate statistics.
    """

    help = ("Usage: statistic --dry-run \n"
            "")

    option_list = BaseCommand.option_list + (
        make_option('-n', '--dry-run',
                    action='store_true', dest='dry_run', default=False,
                    help="Do everything except writing files. "),
    )

    def handle(self, *args, **options):

        dry_run = options['dry_run']

        if len(args) == 0:
            print "Init OK"
        else:
            print self.help
            return

        
        if dry_run:
            print "Doing a dry run."
        fullstat()

       


coursemap = {
    u'CPM/Astr012013/2013-2014' : u'Астрономия',
    u'CPM/Bi012013/2013-2014' : u'Биология',
    #u'CPM/EDX_01/2013-2014' : u'',
    u'CPM/Eco012013/2013-2014' : u'Экология',
    u'CPM/Econom012013/2013-2014' : u'Экономика',
    #u'CPM/Econom022013/2013-2014' : u'',
    u'CPM/En012013/2013-2014' : u'Английский язык',
    #u'CPM/En02/2013' : u'',
    u'CPM/French012013/2013-2014' : u'Французский язык',
    u'CPM/Geo02_2013/2013-2014' : u'География',
    u'CPM/Hist012013/2013-2014' : u'История',
    #u'CPM/Hist022013/2013-2014' : u'',
    u'CPM/Lit01/2013-2014' : u'Литература',
    #u'CPM/Lit022013/2013-2014' : u'',
    u'CPM/MXK012013/2013-2014' : u'Искусство (МХК)',
    u'CPM/Ma01_2013/2013-2014' : u'Математика',
    #u'CPM/Mus012013/2013-2014' : u'',
    u'CPM/Nem012013/2013-2014' : u'Немецкий язык',
    u'CPM/OBG012013/2013-2014' : u'ОБЖ',
    #u'CPM/PID01/2013-2014' : u'',
    u'CPM/Pravo012013/2013-2014' : u'Право',
    #u'CPM/Pravo022013/2013-2014' : u'',
    #u'CPM/Psi012013/2013-2014' : u'',
    u'CPM/Russian001/2013' : u'Русский язык',
    u'CPM/Techno012013/2013-2014' : u'Технология',
    u'CPM/chemistry01/2013' : u'Химия',
    #u'CPM/french01/2013' : u'Французский язык',
    u'CPM/gym01/2013' : u'Физическая культура',
    u'CPM/inf07/2013-2014' : u'Информатика',
    u'CPM/physics01/2013' : u'Физика',
    u'CPM/socio01/2013' : u'Обществознание',
    u'CPM/volimp01/2013' : u'Вводный курс',
}

def gendata(request):
    data = {}
    for course in modulestore().get_courses():
        data[course.id] = {}
        if course.id not in coursemap:
            continue
        print("Loading info for course {courseid}".format(courseid = course.id))
        
        enrolled_students = User.objects.filter(
            courseenrollment__course_id=course.id,
        ).prefetch_related("groups").order_by('username')

        if enrolled_students.count() <= 0:
            continue

        #Category weights
        gradeset = student_grades(enrolled_students[0], request, course, keep_raw_scores=False, use_offline=False)
        category_weights = {}

        for section in gradeset['grade_breakdown']:
            category_weights[section['category']] = section['weight']    

        for user in enrolled_students:
            data[course.id][user.email] = {}

            #User
            data[course.id][user.email]["user"] = user

            #Raw statistic by problems
            gradeset = student_grades(user, request, course, keep_raw_scores=True, use_offline=False)
            statprob = [(getattr(score, 'earned', '') or score[0]) for score in gradeset['raw_scores']]
            
            #By subsection
            statsec = []

            courseware_summary = grades.progress_summary(user, request, course);
            complition = 0
            complition_cnt = 0
            for chapter in courseware_summary:
                total = 0
                flag = False
                for section in chapter['sections']:
                    if not section['graded'] or len(section['format']) < 1:
                        continue
                    flag = True
                    statsec += [((section['section_total'].earned / section['section_total'].possible) if section['section_total'].possible else 0)]
                    total += ((section['section_total'].earned / section['section_total'].possible) if section['section_total'].possible else 0) * category_weights.get(section['format'], 0.0)
                statsec += [total]
                if flag:
                    complition += total
                    complition_cnt += 1
            if complition_cnt == 0:
                complition = 0
            else:
                complition = complition / complition_cnt
            if complition > 0.7:
                data[course.id][user.email]["0.7"] =  True
            else:
                data[course.id][user.email]["0.7"] =  False
            
            if complition > 0.99:
                data[course.id][user.email]["1.0"] =  True
            else:
                data[course.id][user.email]["1.0"] =  False

            data[course.id][user.email]["prob_info"] = statprob
            data[course.id][user.email]["sec_info"] = statsec
    return data


def fullstat(request = None):


    request = DummyRequest()
    

    header = [u'ФИО', u'ФИО (измененное)', u'логин школы', u'email', u'email (измененное)', u'курс', u'зарегистрирован', u'2/3', u'100%', u'Задачи/Задания(Модули)']
    assignments = []
    datatable = {'header': header, 'assignments': assignments, 'students': []}
    data = []

    for course_id, course_name in coursemap.iteritems():
        course = get_course(course_id)
    
        datarow = [u'-', u'-', u'-', u'-', u'-', course_name, u'-', u'-', u'-']
        
        assignments = []
        
        enrolled_students = User.objects.filter(
            courseenrollment__course_id=course_id,
        ).prefetch_related("groups").order_by('username')


        gradeset = student_grades(enrolled_students[0], request, course, keep_raw_scores=True, use_offline=False)
        courseware_summary = grades.progress_summary(enrolled_students[0], request, course);


        assignments += [score.section for score in gradeset['raw_scores']]
        
        for chapter in courseware_summary:
            for section in chapter['sections']:
                if not section['graded'] or len(section['format']) < 1:
                    continue
                assignments += [section['format']]
            assignments += [chapter['display_name']]

        datarow += assignments
        data.append(datarow)
        

    edxdata = gendata(request)

    f = open("/opt/data.csv")

    if f is None:
        return False;

    ff = UnicodeDictReader(f, delimiter=';', quoting=csv.QUOTE_NONE)

    idx = 0
    for row in ff:
        try:
            idx += 1

            datarow = []

            try:
                user = User.objects.filter(email=row['email'])[0];
            except:
                try:
                    user = User.objects.filter(profile__meta__contains = row['email'])[0];
                except:
                    print("No user found on line {0}".format(idx))

            found = False
            for course_id, course_name in coursemap.iteritems():
                if course_name in row['subject']:
                    found = True
                    break
            if not found:
                continue

            #User
            name = row['second-name'] + ' ' + row['first-name'] + ' ' + row['patronymic']
            datarow += [name]
            if user.profile.name != name:
                datarow += [user.profile.name]
            else:
                datarow += [u'']
            datarow += [row['login']]
            datarow += [row['email']]
            if user.email != row['email']:
                datarow += [user.email]
            else:
                datarow += [u'']
            #Course
            course = get_course(course_id)
            datarow += [course_name]

            try:
                user.courseenrollment_set.filter(course_id = course_id)[0]
                datarow += [u'Да']
            except:
                datarow += [u'Нет']
                data.append(datarow)
                continue
            
            #Raw statistic by problems
            statprob = edxdata[course_id][user.email]["prob_info"]
            
            #By subsection
            statsec = edxdata[course_id][user.email]["sec_info"]

            if edxdata[course_id][user.email]["0.7"]:
                datarow += [u"Да"]
            else:
                datarow += [u"Нет"]
            
            if edxdata[course_id][user.email]["1.0"]:
                datarow += [u"Да"]
            else:
                datarow += [u"Нет"]

            datarow += statprob
            datarow += statsec
            
            data.append(datarow)
        except:
            pass
    datatable['data'] = data
    return_csv('full_stat.csv',datatable, open("/var/www/edx/fullstat.csv", "wb"))



    f = open("/opt/data.csv")

    if f is None:
        return False;

    ff = UnicodeDictReader(f, delimiter=';', quoting=csv.QUOTE_NONE)


    usermap = {}
    idx = 0
    for row in ff:
        idx += 1
        usermap.setdefault(row['email'],[]).append(row)

    for course in modulestore().get_courses():

        enrolled_students = User.objects.filter(
            courseenrollment__course_id=course.id,
            courseenrollment__is_active=1,
        ).prefetch_related("groups").order_by('username')


        assignments = []
        
        enrolled_students = User.objects.filter(
            courseenrollment__course_id=course_id,
        ).prefetch_related("groups").order_by('username')


        gradeset = student_grades(enrolled_students[0], request, course, keep_raw_scores=True, use_offline=False)
        courseware_summary = grades.progress_summary(enrolled_students[0], request, course);


        assignments += [score.section for score in gradeset['raw_scores']]
        
        for chapter in courseware_summary:
            for section in chapter['sections']:
                if not section['graded'] or len(section['format']) < 1:
                    continue
                assignments += [section['format']]
            assignments += [chapter['display_name']]

        header = [u'ФИО', u'логин школы', u'email', u'2/3', u'100%']
        header += assignments
        datatable = {'header': header, 'assignments': assignments, 'students': []}
        data = []
                
        for user in enrolled_students:
            try:
                datarow = []

                #User
                name = user.profile.name
                datarow += [name]
                datarow += [user.profile.work_login]
                datarow += [user.email]
                
                #Raw statistic by problems
                statprob = edxdata[course_id][user.email]["prob_info"]
                
                #By subsection
                statsec = edxdata[course_id][user.email]["sec_info"]

                if edxdata[course_id][user.email]["0.7"]:
                    datarow += [u"Да"]
                else:
                    datarow += [u"Нет"]
                
                if edxdata[course_id][user.email]["1.0"]:
                    datarow += [u"Да"]
                else:
                    datarow += [u"Нет"]

                datarow += statprob
                datarow += statsec
                
                data.append(datarow)
            except:
                pass
        datatable['data'] = data
        return_csv(course.id,datatable, open("/var/www/edx/" + course.id.replace('/','_') + ".xls", "wb"))

    return True


def UnicodeDictReader(utf8_data, **kwargs):
    csv_reader = csv.DictReader(utf8_data, **kwargs)
    for row in csv_reader:
        yield dict([(key, unicode(value, 'utf-8')) for key, value in row.iteritems()])  


def return_csv(func, datatable, file_pointer=None):
    """Outputs a CSV file from the contents of a datatable."""
    if file_pointer is None:
        return None
    else:
        response = file_pointer
    writer = csv.writer(response, dialect='excel-tab', quotechar='"', quoting=csv.QUOTE_ALL)
    encoded_row = [unicode(s).encode('cp1251') for s in datatable['header']]
    writer.writerow(encoded_row)
    for datarow in datatable['data']:
        encoded_row = [unicode(s).encode('cp1251') for s in datarow]
        writer.writerow(encoded_row)
    return response


def progressbar(cnt, total):
    i = (cnt * 20) / total
    sys.stdout.write('\r')
    sys.stdout.write("[%-20s] %d%%" % ('='*i, 5*i))
    sys.stdout.flush()


class DummyRequest(object):
    """Dummy request"""

    META = {}

    def __init__(self):
        self.session = {}
        self.user = None
        self.host = None
        self.secure = True

    def get_host(self):
        """Return a default host."""
        return self.host

    def is_secure(self):
        """Always secure."""
        return self.secure
