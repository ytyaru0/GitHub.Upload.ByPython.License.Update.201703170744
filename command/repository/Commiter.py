#!python3
#encoding:utf-8
import subprocess
import shlex
import time
import requests
import json
import Data
import os.path

class Commiter:
    def __init__(self, data):
        self.data = data

    def ShowCommitFiles(self):
#        subprocess.call(shlex.split("git add -n ."))
        self.files = self.__GetCommitFiles(is_show=True, is_debug_show=False)

    """
    git管理追加ファイル一覧を取得する。
    以下のような出力文字列から。
    add 'GitHub.Repositories.ytyaru0.sqlite3'
    add 'ReadMe.md'
    add 'command/repository/Commiter.py'
    @param  {boolean} is_showは`git add -n .`の出力結果を表示するか否か。
    @param  {boolean} is_debug_showは返却するファイル一覧を表示するか否か。
    @return {string[]} gitにステージングするファイル一覧の相対パス
    """
    def __GetCommitFiles(self, is_show=False, is_debug_show=False):
        p = subprocess.Popen("git add -n .", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_data, stderr_data = p.communicate()
        stdout_data = stdout_data.decode('utf-8')
        # 改行コードを'\n'に統一する
        stdout_data = stdout_data.replace('\r\n', '\n')
        stdout_data = stdout_data.replace('\r', '\n')
        # 最終文字の'\n'を削除する
        stdout_data = stdout_data[:-1]
        if is_show:
            print(stdout_data)
        
        # 配列化
        files = []
        for line in stdout_data.split('\n'):
            if 0 < len(line):
                files.append("./" + line.replace("add '", "")[:-1])
        if is_debug_show:
            for f in files:
                print(f)
        return files
        
    def AddCommitPush(self, commit_message):
        subprocess.call(shlex.split("git add ."))
        subprocess.call(shlex.split("git commit -m '{0}'".format(commit_message)))
        subprocess.call(shlex.split("git push origin master"))
        time.sleep(3)
        self.__InsertLanguages(self.__GetLanguages())
#        self.__InsertLicense()
        self.__InsertUpdateLicense()

    def __GetLanguages(self):
        url = 'https://api.github.com/repos/{0}/{1}/languages'.format(self.data.get_username(), self.data.get_repo_name())
        r = requests.get(url)
        if 300 <= r.status_code:
            print(r.status_code)
            print(r.text)
            print(url)
            raise Exception("HTTP Error {0}".format(r.status_code))
            return None
        else:
            print(r.text)
            return json.loads(r.text)

    def __InsertLanguages(self, j):
        self.data.db_repo.begin()
        repo_id = self.data.db_repo['Repositories'].find_one(Name=self.data.get_repo_name())['Id']
        self.data.db_repo['Languages'].delete(RepositoryId=repo_id)
        for key in j.keys():
            self.data.db_repo['Languages'].insert(dict(
                RepositoryId=repo_id,
                Language=key,
                Size=j[key]
            ))
        self.data.db_repo.commit()

    """
    リポジトリのライセンス情報を挿入または更新する。
    """
    def __InsertUpdateLicense(self):
        # リポジトリのライセンス情報を取得する
#        j = self.__RequestRepository()
#        license_id = self.__GetLicenseId(j)
        
        repo = self.data.db_repo['Repositories'].find_one(Name=self.data.get_repo_name())
#        repo = self.data.db_repo['Repositories'].find_one(IdOnGitHub=j['id'])
        if None is repo:
            raise Exception('対象リポジトリのレコードが存在しません。正常動作では必ずリポジトリ新規作成時にレコードが作成されるはずです。')
        
        # リポジトリのライセンスレコードが存在しないならDBに挿入する
        if None is self.data.db_repo['Licenses'].find_one(RepositoryId=repo['Id']):
            print('挿入する-----------------------')
            self.__InsertLicense()
        else:
            # 今回のadd対象にライセンスファイルが存在するならDBを更新する
            if self.__ContaintLicenseFile():
                print('更新する-----------------------')
                self.__UpdateLicense()

    """
    `git add`対象にライセンスファイルが含まれているか否か。
    @return {boolean} True:含まれる False:含まれない
    """
    def __ContaintLicenseFile(self):
        for f in self.files:
            filename = os.path.basename(f)
            if ("LICENSE" == filename or
                "LICENSE.txt" == filename or 
                "LICENSE.md" == filename or 
                "LICENSE.TXT" == filename or 
                "LICENSE.MD" == filename or 
                "COPYING" == filename or
                "COPYING.txt" == filename or 
                "COPYING.md" == filename or
                "COPYING.TXT" == filename or 
                "COPYING.MD" == filename
            ):
                return True
        return False

    def __UpdateLicense(self):
        # リポジトリのライセンス情報を取得する
        j = self.__RequestRepository()
        license_id = self.__GetLicenseId(j)
        # 更新する
        self.data.db_repo.begin()
#        self.data.db_repo['Licenses'].delete(IdOnGitHub=j['id'])
        repo_id = self.data.db_repo['Repositories'].find_one(IdOnGitHub=j['id'])['Id']
        self.data.db_repo['Licenses'].delete(RepositoryId=repo_id)
        self.data.db_repo['Licenses'].insert(dict(
            RepositoryId=repo_id,
            LicenseId=license_id
        ))
        self.data.db_repo.commit()

    def __InsertLicense(self):
        # リポジトリのライセンス情報を取得する
        j = self.__RequestRepository()
        license_id = self.__GetLicenseId(j)
        # リポジトリとライセンスを紐付ける
        self.data.db_repo['Licenses'].insert(dict(
            RepositoryId=self.data.db_repo['Repositories'].find_one(IdOnGitHub=j['id'])['Id'],
            LicenseId=license_id
        ))
    
    """
    このリポジトリに紐付けるべきライセンスのIDを返す。
    """
    def __GetLicenseId(self, j):
        if None is j['license']:
            license_id = None
        else:
            # マスターDBにないライセンスならAPIで取得する
            if None is self.data.db_license['Licenses'].find_one(Key=j['license']['key']):
                license = self.__RequestLicense(j['license']['key'])
                self.data.db_license['Licenses'].insert(self.__CreateRecordLicense(license))
            license_id = self.data.db_license['Licenses'].find_one(Key=j['license']['key'])['Id']
        return license_id

    def __RequestRepository(self):
        url = 'https://api.github.com/repos/{0}/{1}'.format(self.data.get_username(), self.data.get_repo_name())
        r = requests.get(url, headers=self.__GetHttpHeaders())
        return self.__ReturnResponse(r, success_code=200)

    def __RequestLicense(self, key):
        url = 'https://api.github.com/licenses/' + key
        r = requests.get(url, headers=self.__GetHttpHeaders())
        return self.__ReturnResponse(r, success_code=200)

    def __CreateRecordLicense(self, j):
        return dict(
            Key=j['key'],
            Name=j['name'],
            SpdxId=j['spdx_id'],
            Url=j['url'],
            HtmlUrl=j['html_url'],
            Featured=self.__BoolToInt(j['featured']),
            Description=j['description'],
            Implementation=j['implementation'],
            Permissions=self.__ArrayToString(j['permissions']),
            Conditions=self.__ArrayToString(j['conditions']),
            Limitations=self.__ArrayToString(j['limitations']),
            Body=j['body']
        )

    def __GetHttpHeaders(self):
        return {
            "Accept": "application/vnd.github.drax-preview+json",
            "Time-Zone": "Asia/Tokyo",
            "Authorization": "token {0}".format(self.data.get_access_token())
        }

    def __ReturnResponse(self, r, success_code=None, sleep_time=2, is_show=True):
        if is_show:
            print("HTTP Status Code: {0}".format(r.status_code))
            print(r.text)
        time.sleep(sleep_time)
        if None is not success_code:
            if (success_code != r.status_code):
                raise Exception('HTTP Error: {0}'.format(r.status_code))
                return None
        return json.loads(r.text)

    def __BoolToInt(self, bool_value):
        if True == bool_value:
            return 1
        else:
            return 0

    def __ArrayToString(self, array):
        ret = ""
        for v in array:
            ret = v + ','
        return ret[:-1]
