#!/bin/env python3

##  by Ralf Brown, Carnegie Mellon University
##  last edit: 08jun2019

import argparse
import json
import os
import re
import sys
from textwrap import wrap
import urllib, urllib.parse, urllib.request
from urllib.error import HTTPError
from time import sleep

######################################################################
####     CONFIGURATION						  ####

HACKERRANK_HOST = "www.hackerrank.com"
API_BASE = "/x/api/v3/"

# HR returns 10 results per page by default, supports a maximum of 100
MAX_PER_PAGE = 50

######################################################################

class HRException(Exception):
    def __init__(self, msg):
        super(HRException,self).__init__(msg)


######################################################################

class HackerRank():
    def __init__(self, host = HACKERRANK_HOST, verbose = False):
        self.hostname = host
        self.api_base = 'https://' + self.hostname + API_BASE
        self.verbose = verbose
        self.dryrun = False
        self.http_error_hook = None
        self.qname_cache = {}
        tokenfile = os.environ['HOME'] + '/.hackerrank_api_token'
        try:
            with open(tokenfile) as f:
                self.token = f.read().strip()
        except Exception as err:
            print(err)
            return
        return

    def run_verbosely(self, verbosity):
        self.verbose = verbosity
        return

    def simulate(self, sim):
        self.dryrun = sim
        return

    @staticmethod
    def has_limit(arglist):
        for a,v in arglist:
            if a == 'limit':
                return True
        return False

    ## staffeli/canvas.py showed how to call REST API
    def mkrequest(self, method, url, arglist, use_JSON_data):
        # convert a relative URL into an absolute URL by appending it to the base URL for the API
        if '://' not in url:
            url = self.api_base + url
        if arglist is None:
            arglist = []
        headers = { 'Authorization': 'Bearer ' + self.token }
        if use_JSON_data:
            if type(arglist) is type(''):
                qstring = ''.join(c if c != '\n' else ' ' for c in arglist)
            else:
                argdict = {}
                for k,v in arglist:
                    argdict[k] = v
                qstring = json.dumps(argdict)
            qstring = qstring.encode('utf-8')
            qstring = qstring.replace(b'"true"',b'true')
            headers['Content-Type'] = 'application/json'
        else:
            # add page-size to request
            if not self.has_limit(arglist):
                arglist.append(('limit',MAX_PER_PAGE))
            qstring = urllib.parse.urlencode(arglist, safe='[]@,', doseq=True).encode('utf-8')
            if method == 'GET':
                if '?' not in url:
                    url = url + '?' + str(qstring,'utf-8')
                qstring = None
        if self.verbose:
            print('{}ing url:'.format(method),url)
            if qstring:
                print("Encoded args:",qstring)
        req = urllib.request.Request(url, data=qstring, method=method, headers=headers)
        return urllib.request.urlopen(req, data=qstring)

    def call_api(self, method, url, arglist=None, all_pages=False, use_JSON_data=False):
        if arglist is None:
            arglist = []
        entries = []
        while url:
            with self.mkrequest(method, url, arglist, use_JSON_data) as f:
                if f.getcode() == 204:  # No Content
                    if self.verbose:
                        print('204 No Content')
                    break
                if f.getcode() == 429:
                    print('429 Rate Limit Exceeded')
                data = json.loads(f.read().decode('utf-8'))
                if not entries:
                    entries = data
                elif 'data' in data:
                    if 'data' in entries:
                        entries['data'] += data['data']
                    else:
                        entries = data
                else:
                    print("can't concatenate!")
                url = data['next'] if 'next' in data else None
                if url == '' or not all_pages:
                    url = None
        return entries

    def get(self,url,arglist=None,fields=None,all_pages=False):
        if fields is not None and fields != [] and fields != '':
            if type(fields) == type([]):
                fields = ','.join(fields)
            if not arglist:
                arglist = [('fields',fields)]
            else:
                arglist.append(('fields',fields))
        try:
            result = self.call_api('GET', url, arglist=arglist, all_pages=all_pages)
        except HTTPError as err:
            if self.http_error_hook:
                self.http_error_hook(err)
            else:
                print(err,'for GET',url)
            result = []
        return result

    def put(self,url,arglist=None):
        if self.dryrun:
            print('DRY RUN: would have PUT',url,'with args:\n',arglist)
            return []
        try:
            return self.call_api('PUT', url, arglist=arglist, use_JSON_data=True)
        except HTTPError as err:
            print(err,'for PUT',url)

    def post(self,url,arglist=None):
        if self.dryrun:
            print('DRY RUN: would have POSTed',url,'with args:\n',arglist)
            return []
        try:
            return self.call_api('POST', url, arglist, use_JSON_data=True)
        except HTTPError as err:
            print(err,'for POST',url)

    # not used by HackerRank API at this time
    def patch(self,url,arglist=None):
        if self.dryrun:
            print('DRY RUN: would have PATCHed',url,'with args:\n',arglist)
            return []
        try:
            return self.call_api('PATCH', url, arglist)
        except HTTPError as err:
            print(err,'for PATCH',url)

    def delete(self,url,arglist=None):
        if self.dryrun:
            print('DRY RUN: would have DELETEd',url,'with args:\n',arglist)
            return []
        try:
            return self.call_api('DELETE', url, arglist)
        except HTTPError as err:
            print(err,'for DELETE',url)

    def options(self,url,arglist=[]):
        try:
            return self.call_api('OPTIONS', url, arglist)
        except HTTPError as err:
            if self.http_error_hook:
                self.http_error_hook(err)
            else:
                print(err,'for OPTIONS',url)
            result = []
        return result

    ## API calls
    def list_users(self):
        return self.get('users',all_pages=True)

    def get_user(self,user_id):
        return self.get('users/{}'.format(user_id))

    def update_user(self,user_id,settings):
        return self.put('users/{}'.format(user_id),arglist=settings)

    def lock_user(self,user_id):
        return self.delete('users/{}'.format(user_id))

    def search_users(self,search_string):
        return self.get('users/search',arglist=[('search',search_string)])

    def create_team(self,settings):
        return self.post('teams',arglist=settings)

    def list_teams(self):
        return self.get('teams',all_pages=True)

    def get_team(self,team_id):
        return self.get('teams/{}'.format(team_id))

    def update_team(self,team_id,settings):
        return self.put('teams/{}'.format(team_id),arglist=settings)

    def delete_team(self,team_id):
        return self.delete('teams/{}'.format(team_id))

    def get_team_members(self,team_id):
        return self.get('teams/{}/users'.format(team_id))

    def check_team_membership(self,team_id,user_id):
        return self.get('teams/{}/users/{}'.format(team_id,user_id))

    def add_team_member(self,team_id,user_id):
        return self.post('teams/{}/users/{}'.format(team_id,user_id))

    def remove_team_member(self,team_id,user_id):
        return self.delete('teams/{}/users/{}'.format(team_id,user_id))

    def list_tests(self):
        t_list = self.get('tests',all_pages=True)
        if 'data' in t_list:
            t_list = t_list['data']
        return t_list

    def create_test(self,settings):
        return self.get('tests',arglist=settings)

    def find_test_id(self,test_name):
        t_list = self.list_tests()
        for t in t_list:
            if 'name' in t and t['name'] == test_name:
                return t['id']
        return -1

    def get_test(self,test_id):
        t_info = self.get('tests/{}'.format(test_id))
        return t_info if t_info else {'id':test_id,'name':"Test not found",'created_at':None,'state':'unknown','locked':None,'draft':None,'starred':None}

    def update_test(self,test_id,settings):
        return self.put('tests/{}'.format(test_id),arglist=settings)

    def delete_test(self,test_id):
        return self.delete('tests/{}'.format(test_id))

    def archive_test(self,test_id):
        return self.post('tests/{}/archive'.format(test_id))

    def list_test_inviters(self,test_id):
        return self.get('tests/{}/inviters'.format(test_id),all_pages=True)

    def list_test_candidates(self,test_id, fields=None, filters=None):
        c_list = self.get('tests/{}/candidates'.format(test_id),arglist=filters,fields=fields,all_pages=True)
        return c_list['data'] if 'data' in c_list else c_list
            
    def invite_test_candidate(self,test_id,fullname,email,msg="",template=None,send_email=True,tags=None,addtime=0):
        arglist=[('email',email),
                 ('send_email',send_email)]
#                 ('send_email','true' if send_email else 'false')]
        if fullname:
            arglist.append(('fullname',fullname))
        if msg and msg != '':
            arglist.append(('message',msg))
        if template:
            arglist.append(('template',template))
        if tags:
            for tag in tags:
                arglist.append(('tags[]',tag))
        if addtime:
            arglist.append(('accommodations','{"additional_time_percent":'+str(addtime)+'}'))
        return self.post('tests/{}/candidates'.format(test_id),arglist)

    def get_all_test_scores(self,test_id,include_incomplete=False,filters=None):
        c_info = self.list_test_candidates(test_id,filters=filters)
        scores = []
        all_qs = set()
        for cand in c_info:
            if 'questions' not in cand:
                continue
            for q in cand['questions']:
                all_qs.add(q)
        for cand in c_info:
            score = cand['score']
            endtime = cand['attempt_endtime']
            if (not score or not endtime) and not include_incomplete:
                continue
            if score == int(score):
                score = int(score)
            id = cand['id']
            fullname = cand['full_name']
            email = cand['email']
            andrew = self.get_Andrew_ID(cand)
            if andrew and andrew[0] == '/':
                andrew = andrew[1:]
            percent = cand['percentage_score']
            questions = cand['questions']
            for q in all_qs:
                if q not in questions:
                    questions[q] = '0'
                elif questions[q] == int(questions[q]):
                    questions[q] = int(questions[q])
            plag = cand['plagiarism'] if cand['plagiarism_status'] == True else None
            scores += [{'id': id, 'fullname': fullname, 'email': email, 'andrew': andrew, 'score': score,
                        'percent': percent, 'questions': questions, 'endtime': endtime, 'plag': plag}]
        return scores

    def get_test_candidate(self,test_id,cand_id, fields=None):
        return self.get('tests/{}/candidates/{}'.format(test_id,cand_id),fields=fields)

    def update_test_candidate(self,test_id,cand_id,fullname,valid_from=None,valid_to=None,metadata=None,tags=None):
        arglist=[('fullname',fullname)]
        if valid_from:
            arglist.append(('invite_valid_from',valid_from))
        if valid_to:
            arglist.append(('invite_valid_to',valid_to))
        if metadata:
            arglist.append(('invite_metadata',metadata))
        if tags:
            pass ## add 'tags[foo]' to arglist
        return self.put('tests/{}/candidates/{}'.format(test_id,cand_id),arglist)

    def get_report_pdf(self,test_id,cand_id):
        return self.get('tests/{}/candidates/{}/pdf'.format(test_id,cand_id))

    def delete_report(self,test_id,cand_id):
        return self.delete('tests/{}/candidates/{}/report'.format(test_id,cand_id))

    def cancel_invite(self,test_id,cand_id):
        return self.delete('tests/{}/candidates/{}/invite'.format(test_id,cand_id))

    def search_candidates(self,test_id,search_str,fields=None,filters=None):
        if filters is None:
            filters = []
        return self.get('tests/{}/candidates/search'.format(test_id),arglist=[('search',search_string)]+filters,
                   fields=fields,all_pages=True)

    def list_interviews(self):
        return self.get('interviews',all_pages=True)

    def create_interview(self,settings):
        return self.post('interviews',arglist=settings)

    def show_interview(self,iview_id,fields=None):
        return self.get('interviews/{}'.format(iview_id),fields=fields)

    def update_interview(self,iview_id,settings):
        return self.put('interviews/{}'.format(iview_id),arglist=settings)

    def delete_interview(self,iview_id,settings):
        return self.delete('interviews/{}'.format(iview_id))

    def list_all_questions(self,qtype=None,tags=None,languages=None):
#        arglist=[('fields','id,name,type,languages,test_case_count,status,created_at')]
#	(requesting a partial response results in empty records for each question!)
        arglist=[]
        if qtype and qtype != '':
            arglist.append(('type',qtype))
        if tags and tags != '':
            arglist.append(('tags',tags))
        if languages and languages != '':
            arglist.append(('languages',languages))
        q_info = self.get('questions',arglist,all_pages=True)
        return q_info['data'] if 'data' in q_info else q_info

    def list_questions(self,type,tags,languages,offset,limit=MAX_PER_PAGE):
        arglist=[]
        if qtype and qtype != '':
            arglist.append(('type',qtype))
        if tags and tags != '':
            arglist.append(('tags',tags))
        if languages and languages != '':
            arglist.append(('languages',languages))
        return self.get('questions',[('offset',offset),('limit',limit)])

    #def create_question(self,settings):

    def show_question(self,q_id,fields=None):
        return self.get('questions/{}'.format(q_id),fields=None)
#  problem with API: specifying partial response results in empty records being returned!
#        return self.get('questions/{}'.format(q_id),fields=fields)

    def get_question_name(self,q_id,verbose=None):
        if q_id in self.qname_cache:
            return self.qname_cache[q_id]
        if verbose is not None:
            orig_verbose = self.verbose
            self.verbose = verbose
        result = self.show_question(q_id,'name')
        if verbose is not None:
            self.verbose = orig_verbose
        if result and 'name' in result:
            name = result['name']
            self.qname_cache[q_id] = name
            return name
        else:
            return '{unknown}'

    #def update_question(self,q_id,settings):

    def list_invite_templates(self):
        t_info = self.get('templates',all_pages=True)
        return t_info['data'] if 'data' in t_info else t_info

    def show_invite_template(self,t_id):
        return self.get('templates/{}'.format(t_id))

    def list_all_audit_logs(self):
        return self.get('audit_log',all_pages=True)

    def list_audit_logs(self,offset=0,limit=MAX_PER_PAGE):
        return self.get('audit_log',[('offset',offset),('limit',limit)])

    @staticmethod
    def late_score(score, late_penalty):
        if late_penalty > 0.0:
            score = int(10.0 * score * (1.0 - late_penalty) + 0.5)/10.0
        if score == int(score):
            score = int(score)
        return score

    def feedback(self, q_info, late_penalty):
        if not q_info:
            return '\t0\tTotal (missing or not yet submitted)'
        fb = ''
        total = 0.0
        for q_num in q_info:
            score = q_info[q_num]
            if score:
                total += float(score)
            q_name = self.get_question_name(q_num)
            if '(' in q_name:
                q_name, _, _ = q_name.rpartition('(')
            fb += '\t{}\t{}\n'.format(score,q_name)
        if total == int(total):
            total = int(total)
        if late_penalty > 0.0:
            total = HackerRank.late_score(total,late_penalty)
        fb += '\t{}\t--total--'.format(total)
        if late_penalty > 0.0:
            fb += ' (after {}% late penalty)'.format(int(100*late_penalty),total)
        return fb


    #### utility functions to help with display
    @staticmethod
    def clean_HTML(text):
        text = re.sub("[<]/?(span|font)[^>]*[>]","",text)
        text = re.sub("[<]/?strong[^>]*[>]","",text)
        text = re.sub("[<]/?em[>]","",text)
        text = re.sub("[<]div [^>]*[>]","<div>",text)
        return text

    @staticmethod
    def get_Andrew_ID(info):
        if 'candidate_details' in info and info['candidate_details']:
            for det in info['candidate_details']:
                if 'field_name' in det and (det['field_name'] == 'andrew_id' or det['field_name'] == 'andrew'):
                    return '/'+det['value']
        return ''
        
    def display_owner(self,info,verbose=False):
        if 'owner' in info:
            if verbose:
                orig_verbose = self.verbose
                self.verbose = False
                owner = self.get_user(info['owner'])
                self.verbose = orig_verbose
                if owner:
                    print("OWNER:\t{} {} ({})".format(owner['firstname'],owner['lastname'],owner['email']))
            else:
                print("OWNER:\t{}\t\t(use -v to get name/email)".format(info['owner']))
        return

    def print_question(self, q_info, verbose, compact):
        if compact:
            if q_info['owner'] == '41872':  ## question by HackerRank?
                return True
            cases = q_info['test_case_count'] if 'test_case_count' in q_info else 0
            label = 'tests'
            if cases == 0 and 'options' in q_info:
                cases = len(q_info['options'])
                label = 'options'
            print("{}: {} {} ({} {}): {}".format(q_info['id'],q_info['status'],q_info['type'],cases,label,
                                                              q_info['name']))
            return True
        print("NAME:\t{}".format(q_info['name']))
        del q_info['name']
        if 'created_at' in q_info:
            print("CREATE:\t{}".format(q_info['created_at']))
            del q_info['created_at']
        print("TYPE:\t{} ({})".format(q_info['type'],q_info['status']))
        del q_info['type']
        del q_info['status']
        if 'sample_test_case_count' in q_info:
            print("TESTS:\t{} ({} sample)".format(q_info['test_case_count'],q_info['sample_test_case_count']))
            del q_info['test_case_count']
            del q_info['sample_test_case_count']
        elif 'test_case_count' in q_info:
            if q_info['test_case_count']:
                print("TESTS:\t{}".format(q_info['test_case_count']))
            del q_info['test_case_count']
        if 'tags' in q_info:
            print("TAGS:\t{}".format(', '.join(q_info['tags'])))
            del q_info['tags']
        print("ID:\t{} (API), {} (unique)".format(q_info['id'],q_info['unique_id']))
        del q_info['id']
        del q_info['unique_id']
        if 'languages' in q_info:
            if q_info['languages']:
                print("LANG:\t{}".format(', '.join(q_info['languages'])))
            del q_info['languages']
        self.display_owner(q_info,verbose)
        del q_info['owner']
        if 'problem_statement' in q_info:
            text = HackerRank.clean_HTML(str(q_info['problem_statement']))
            print("PROB:\t{}".format('\n\t'.join(wrap(text,100))))
            del q_info['problem_statement']
        if 'answer' in q_info and 'options' in q_info:
            answer = q_info['answer']
            print("ANS:",end='')
            for n, opt in enumerate(q_info['options']):
                print('\t{} {}'.format('*' if (n+1)==answer else ' ',opt))
            del q_info['answer']
            del q_info['options']
        for key in q_info:
            print("{}:\t{:.100}".format(key,str(q_info[key])))
        return True

    @staticmethod
    def extract_plagiarism(info):
        if not info:
            return {}
        plag = info['plag']
        if 'plagiarism' in plag:
            plag = plag['plagiarism']
            if 'status' in plag and plag['status'] != True:
                return {}
            if 'questions' in plag:
                plag = plag['questions']
            # run through all of the flagged questions
            suspects = []
            for q in plag:
                for other in plag[q]:
                    s_info = plag[q][other]['occurances']
                    for sol in s_info:
                        suspects += [(q,s_info[sol]['email'],s_info[sol]['probability'])]
            fullname = info['fullname']
            email = info['email']
            andrew = info['andrew']
            return {'fullname':fullname,'email':email,'andrew':andrew,'suspects':suspects}
        else:
            return {}


    @staticmethod
    def display_invite_template(template):
        print(template['name'])
        is_default = ''
        if 'default' in template and template['default'] == True:
            is_default = ' (default)'
        print('\tID:\t{}{}'.format(template['id'],is_default))
        if 'subject' in template and template['subject']:
            print('\tSubj:\t{}'.format(template['subject']))
        create = template['created_at']
        update = template['updated_at'] if 'updated_at' in template else create
        print('\tDate:\t{} / {}'.format(create,update))
        text = template['content'] if 'content' in template else ''
        print('\t{}'.format('\n\t'.join(wrap(text,100))))
        print()

    #### user-level commands: information retrieval

    @staticmethod
    def display_tests(args):
        hr = HackerRank(verbose=args.verbose)
        t_list = hr.list_tests()
        for t in t_list:
            print('{}:\t{}'.format(t['id'],t['name']))
        return True

    @staticmethod
    def display_test(args, t_id):
        hr = HackerRank(verbose=args.verbose)
        t_info = hr.get_test(t_id)
        print("NAME:\t{}".format(t_info['name']))
        del t_info['name']
        if not 'unique_id' in t_info:
            return True
        lock = 'locked' if 'locked' in t_info and t_info['locked'] else 'unlocked'
        draft = 'draft' if 'draft' in t_info and t_info['draft'] else 'published'
        star = 'starred' if 'starred' in t_info and t_info['starred'] else 'unstarred'
        print("STATUS:\t{} - {} - {} - {}".format(t_info['state'],lock,draft,star))
        del t_info['state']
        del t_info['locked']
        del t_info['draft']
        del t_info['starred']
        print("ID:\t{} (API), {} (unique)".format(t_info['id'],t_info['unique_id']))
        del t_info['id']
        del t_info['unique_id']
        print("CREATE:\t{}".format(t_info['created_at']))
        del t_info['created_at']
        start = t_info['start_time'] if 'start_time' in t_info else 'always'
        stop =  t_info['end_time'] if 'end_time' in t_info else 'forever'
        print("TIME:\t{}m - {} - {}".format(t_info['duration'],start,stop))
        del t_info['duration']
        del t_info['start_time']
        del t_info['end_time']
        if 'tags' in t_info:
            print("TAGS:\t{}".format(', '.join(t_info['tags'])))
            del t_info['tags']
        hr.display_owner(t_info,args.verbose)
        del t_info['owner']
        if 'instructions' in t_info:
            text = HackerRank.clean_HTML(str(t_info['instructions']))
            print("INST:\t{}".format('\n\t'.join(wrap(text,100))))
            del t_info['instructions']
        if args.verbose:
            names = []
            for q in t_info['questions']:
                names += ["{}: {}".format(q,hr.get_question_name(q,verbose=False))]
            print("Q:\t{}".format('\n\t'.join(names)))
        else:
            print("Q:\t{}".format(', '.join(t_info['questions'])))
        del t_info['questions']
        for key in t_info:
            print('{}:\t{}'.format(key,t_info[key]))
        return True

    @staticmethod
    def display_user_list(args):
        hr = HackerRank(verbose=args.verbose)
        u_list = hr.list_users()
        if 'data' in u_list:
            u_list = u_list['data']
        for u in u_list:
            print('{}\t{} {} ({})'.format(u['id'],u['firstname'],u['lastname'],u['email']))
        return True

    @staticmethod
    def display_user(args, u_id):
        hr = HackerRank(verbose=args.verbose)
        u_info = hr.get_user(u_id)
        print('{}\t{} {} ({}) - {} - {}'.format(u_info['id'],u_info['firstname'],u_info['lastname'],u_info['email'],
                                                u_info['status'],u_info['role']))
        del u_info['id']
        del u_info['firstname']
        del u_info['lastname']
        del u_info['email']
        del u_info['status']
        del u_info['role']
        last_time = 'never'
        if 'last_activity_time' in u_info:
            last_time = u_info['last_activity_time']
        print('ACTIVE:\t{} - {}'.format(u_info['activated'],last_time))
        del u_info['activated']
        del u_info['last_activity_time']
        print('ADMIN:\tcompany={}, team={}'.format(u_info['company_admin'],u_info['team_admin']))
        del u_info['company_admin']
        del u_info['team_admin']
        perm = []
        for x in ['tests','questions','interviews','candidates','shared_tests','shared_questions','shared_interviews','shared_candidates']:
            if x+'_permission' in u_info:
                perm += ['{}:{}'.format(x,u_info[x+'_permission'])]
                del u_info[x+'_permission']
        if perm:
            print("PERM:\t{}".format('\n\t'.join(wrap(', '.join(perm),70))))
        if 'teams' in u_info:
            print("TEAMS:\t{}".format(', '.join(u_info['teams'])))
            del u_info['teams']
        for key in u_info:
            print('{}:\t{}'.format(key,u_info[key]))
        return True

    @staticmethod
    def display_all_questions(args):
        hr = HackerRank(verbose=args.verbose)
        q_list = hr.list_all_questions()
        for q in q_list:
            hr.print_question(q,args.verbose,args.terse)
            if not args.terse:
                print()
        return True

    @staticmethod
    def display_question(args, q_id):
        hr = HackerRank(verbose=args.verbose)
        q_info = hr.show_question(q_id)
        if not q_info:
            print("No such question")
            return True
        hr.print_question(q_info,args.verbose)
        return True

    @staticmethod
    def display_test_candidates(args, t_id):
        hr = HackerRank(verbose=args.verbose)
        c_list = hr.list_test_candidates(t_id)
        for c in c_list:
            fname = c['full_name'] if 'full_name' in c else '{unknown}'
            andrew = HackerRank.get_Andrew_ID(c)
            plag = '**' if 'plagiarism_status' in c and c['plagiarism_status'] else '' 
            print('{}: {}{} ({}) - {}{}% @ {}'.format(c['id'],fname,andrew,c['email'],plag,c['percentage_score'],
                                                    c['attempt_endtime']))
        return True

    @staticmethod
    def display_all_scores(args, t_id):
        hr = HackerRank()
        c_info = hr.get_all_test_scores(t_id,args.verbose)
        for cand in c_info:
            print('{} ({}) {}  @ {}'.format(cand['fullname'],cand['email'],cand['andrew'],cand['endtime']))
            questions = cand['questions']
            for q in questions:
                print('\t{}\t{}'.format(questions[q],hr.get_question_name(q)))
            print('{}%\t{}\tTotal{}'.format(cand['percent'],cand['score'],'\t** Plagiarism flagged!' if cand['plag'] else ''))
        return True

    @staticmethod
    def display_score_details(args, t_id, c_id):
        hr = HackerRank(verbose=args.verbose)
        c_info = hr.get_test_candidate(t_id,c_id)
        fname = c_info['full_name'] if 'full_name' in c_info else '{unknown}'
        andrew = HackerRank.get_Andrew_ID(c_info)
        plag = 'plagiarism_status' in c_info and c_info['plagiarism_status'] == True
        percent = c_info['percentage_score']
        questions = c_info['questions']
        for q in questions:
            # cache the question names
            hr.get_question_name(q)
        print('{}{} ({}) @ {}'.format(fname,andrew,c_info['email'],c_info['attempt_endtime']))
        for q in questions:
            print('\t{}\t{}'.format(questions[q],hr.get_question_name(q)))
        print('{}%\t{}\tTotal'.format(percent,c_info['score']))
        if plag:
            print('*** Plagiarism flagged! ***')
            print(c_info['plagiarism'])
        return True

    @staticmethod
    def display_plagiarism(args, t_id):
        hr = HackerRank(verbose=args.verbose)
        filters = [('plagiarism_status','true')]
        p_info = [HackerRank.extract_plagiarism(c) for c in hr.get_all_test_scores(t_id,filters=filters) if c['plag']]
        for p in p_info:
            print('{}/{} ({})'.format(p['fullname'],p['andrew'],p['email']))
            for s in p['suspects']:
                print('\t{} - {}% on {}: {}'.format(s[1],int(s[2]),s[0],hr.get_question_name(s[0])))
        return True
        
    @staticmethod
    def display_templates(args):
        hr = HackerRank(verbose=args.verbose)
        t_info = hr.list_invite_templates()
        for template in t_info:
            HackerRank.display_invite_template(template)
        return True

    @staticmethod
    def display_a_template(args,t_id):
        hr = HackerRank(verbose=args.verbose)
        t_info = hr.show_invite_template(t_id)
        if t_info:
            HackerRank.display_invite_template(t_info)
        return True

    @staticmethod
    def display_invite(args,t_id,candidates):
        hr = HackerRank(verbose=args.verbose)
        hr.simulate(args.dryrun)
        msg = args.message
        for cand in candidates:
            print('Inviting',cand)
            response = hr.invite_test_candidate(t_id,None,cand,msg)
            print('==>',response)
        return True

    #### user-level commands: raw API access
    @staticmethod
    def display_get(args, endpoint, arglist=[]):
        if len(arglist) % 2 != 0:
            print('must have matched parameter/value pairs')
            return
        hr = HackerRank(verbose=args.verbose)
        params = list(zip(arglist[0::2],arglist[1::2]))
        results = hr.get(endpoint,params,all_pages=args.all)
        print(results)
        return True

    @staticmethod
    def display_post(args, endpoint, arglist=[]):
        if len(arglist) % 2 != 0:
            print('must have matched parameter/value pairs')
            return True
        hr = HackerRank(verbose=args.verbose)
        hr.simulate(args.dryrun)
        params = list(zip(arglist[0::2],arglist[1::2]))
        results = hr.post(endpoint,params)
        print(results)
        return True

    @staticmethod
    def display_put(args, endpoint, arglist=[]):
        if len(arglist) % 2 != 0:
            print('must have matched parameter/value pairs')
            return True
        hr = HackerRank(verbose=args.verbose)
        hr.simulate(args.dryrun)
        params = list(zip(arglist[0::2],arglist[1::2]))
        results = hr.put(endpoint,params)
        print(results)
        return True

    @staticmethod
    def display_delete(args, endpoint, arglist=[]):
        if len(arglist) % 2 != 0:
            print('must have matched parameter/value pairs')
            return True
        hr = HackerRank(verbose=args.verbose)
        hr.simulate(args.dryrun)
        params = list(zip(arglist[0::2],arglist[1::2]))
        results = hr.delete(endpoint,params)
        print(results)
        return True

    @staticmethod
    def process_generic_commands(args, remargs):
        if args.showquestion:
            if len(remargs) < 1:
                print("Usage: --showquestion {question_id}")
                return True
            return HackerRank.display_question(args, remargs[0])
        if args.listquestions:
            return HackerRank.display_all_questions(args)
        if args.user:
            if len(remargs) < 1:
                print("Usage: --user {user_id}")
                return True
            return HackerRank.display_user(args, remargs[0])
        if args.listusers:
            return HackerRank.display_user_list(args)
        if args.listtests:
            return HackerRank.display_tests(args)
        if args.templates:
            return HackerRank.display_templates(args)
        if args.showtemplate:
            if len(remargs) < 1:
                print("Usage: --showtemplate {template_id}")
                return True
            return HackerRank.display_a_template(args, remargs[0])
        if args.showtest:
            if len(remargs) < 1:
                print("Usage: --showtest {test_id}")
                return True
            return HackerRank.display_test(args, remargs[0])
        if args.testscore:
            if len(remargs) < 1:
                print("Usage: --testscore {test_id} {candidate_id}")
                return True
            return HackerRank.display_score_details(args, remargs[0], remargs[1])
        if args.listcandidates:
            if len(remargs) < 1:
                print("Usage: --listcandidates {test_id}")
                return True
            return HackerRank.display_test_candidates(args, remargs[0])
        if args.candidatedetails:
            if len(remargs) < 1:
                print("Usage: --candidate_details {candidate_id}")
                return True
            return HackerRank.display_all_scores(args, remargs[0])
        if args.plagiarism:
            if len(remargs) < 1:
                print("Usage: --plagiarism {test_id}")
                return True
            return HackerRank.display_plagiarism(args, remargs[0])
        if args.invite:
            if len(remargs) < 2:
                print("Usage: --invite {test_id} {email} [{email} ...]")
                return True
            return HackerRank.display_invite(args, remargs[0], remargs[1:])
        ## process the raw API requests
        if args.get is True:
            if len(remargs) < 1:
                print("Usage: --get {endpoint} [arg1 val1 [arg2 val2 ...]]")
                return True
            return HackerRank.display_get(args, remargs[0],remargs[1:])
        if args.post is True:
            if len(remargs) < 1:
                print("Usage: --post {endpoint} [arg1 val1 [arg2 val2 ...]]")
                return True
            return HackerRank.display_post(args, remargs[0], remargs[1:])
        if args.put is True:
            if len(remargs) < 1:
                print("Usage: --put {endpoint} [arg1 val1 [arg2 val2 ...]]")
                return True
            return HackerRank.display_put(args, remargs[0], remargs[1:])
        if args.delete is True:
            if len(remargs) < 1:
                print("Usage: --delete {endpoint} [arg1 val1 [arg2 val2 ...]]")
                return True
            return HackerRank.display_delete(args, remargs[0], remargs[1:])
        return False

    @staticmethod
    def parse_arguments(flag_adder = None):
        parser = argparse.ArgumentParser(description="Commandline control of HackerRank account")
        parser.add_argument("-n","--dryrun",action="store_true",help="do everything except actually change values on server")
        parser.add_argument("-v","--verbose",action="store_true",help="run with verbose output")
        ## useful informational functions
        parser.add_argument("--listquestions",action="store_true",help="show list of all test questions")
        parser.add_argument("-Q","--showquestion",action="store_true",help="display test question")
        parser.add_argument("-U","--listusers",action="store_true",help="return a list of user IDs")
        parser.add_argument("-u","--user",action="store_true",help="show information about a specific user")
        parser.add_argument("-T","--listtests",action="store_true",help="list available tests")
        parser.add_argument("-t","--showtest",action="store_true",help="display details of a test")
        parser.add_argument("-c","--listcandidates",action="store_true",help="display list of candidates taking test")
        parser.add_argument("-C","--candidatedetails",action="store_true",help="display detailed results of candidates taking test")
        parser.add_argument("-S","--testscore",action="store_true",help="display detailed score on test T by candidate C")
        parser.add_argument("-P","--plagiarism",action="store_true",help="analyze plagiarism flags for test")
        parser.add_argument("--templates",action="store_true",help="display all invitation templates")
        parser.add_argument("--showtemplate",action="store_true",help="display specified invitation template")

        parser.add_argument("--terse",action="store_true",help="compact display of key items only")

        ## management functions
        parser.add_argument("--invite",action="store_true",help="send invitation to test T to candidates C1,C2...")
        parser.add_argument("--message",metavar="MSG",help="set custom message for invitation")

        ## raw API access for experimenting
        parser.add_argument("--get",action="store_true",help="perform a raw API 'get' call")
        parser.add_argument("--put",action="store_true",help="perform a raw API 'put' call (USE CAUTION!)")
        parser.add_argument("--post",action="store_true",help="perform a raw API 'post' call (USE CAUTION!)")
        parser.add_argument("--delete",action="store_true",help="perform a raw API 'delete' call (USE CAUTION!)")
        parser.add_argument("--all",action="store_true",help="retrieve all pages for a GET request -- may be very slow")
        if flag_adder:
            if type(flag_adder) is type([]):
                for adder in flag_adder:
                    adder(parser)
            else:
                flag_adder(parser)
        if len(sys.argv) <= 1:
            parser.print_usage()
            parser.exit()
        args, remargs = parser.parse_known_args()
        if 'all' not in args:
            args.all = False
        return args, remargs
        
def main():
    args, remargs = HackerRank.parse_arguments()
    if HackerRank.process_generic_commands(args,remargs):
        return
    else:
        print('This sample interface only supports the built-in display functions.')
    return

if __name__ == '__main__':
    main()

