from bs4 import BeautifulSoup
import requests
from queue import Queue
import threading
import time


SLEEP_TIME = 120
FIRST_SLEEP = 15

class DependencyDownloader:

    def __init__(self):
        self.download_queue = Queue()
        self.version_checking_queue = Queue()
        self.pom_queue = Queue()

    def __parse_pom(self, url):
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
        r = requests.get(url, headers=headers)
        if r.status_code >= 200 and r.status_code <= 299:
            data = r.text
            soup = BeautifulSoup(data, 'lxml')
            print('getting pom {}'.format(url))

            dependencies = soup.findAll('dependency')
            for dependency in dependencies:
                if dependency.has_key('version'):
                    groupid = dependency.find('groupid').text
                    artifact = dependency.find('artifactid').text
                    version = dependency.find('version').text
                    link = '{}:{}:{}'.format(groupid, artifact, version)
                    self.add_gradle_to_queue(link)
                else:
                    groupid = dependency.find('groupid').text
                    artifact = dependency.find('artifactid').text
                    link = '{}:{}'.format(groupid, artifact)
                    self.version_checking_queue.put(link)
        else:
            self.pom_queue.put(url)
            print('pom sleeping! ' + url)

    def __check_version(self, url):
        gradle = url.split(":")
        artifact = gradle[0]
        name = gradle[1]
        google_repos = requests.get('https://dl.google.com/dl/android/maven2/master-index.xml').text
        soup = BeautifulSoup(google_repos, 'html.parser')
        tags = [tag.name for tag in soup.find_all()]
        link = artifact.replace('.', '/')

        if any(artifact in s for s in tags):
            group_index = 'https://dl.google.com/dl/android/maven2/{}/group-index.xml'.format(link)
            group_request = requests.get(group_index).text
            group_soup = BeautifulSoup(group_request, 'html.parser')
            group_tags = [tag.name for tag in group_soup.find_all()]
            for tag in group_tags:
                if tag == name:
                    versions = group_soup.find(tag).attrs['versions']
                    version = str(versions).split(',')[0]
                    name_version = '{}-{}'.format(name, version)
                    google_link_pom = 'https://maven.google.com/{}/{}/{}/{}.pom'.format(link, name, version, name_version)
                    google_link_jar = 'https://maven.google.com/{}/{}/{}/{}.jar'.format(link, name, version, name_version)
                    google_link_aar = 'https://maven.google.com/{}/{}/{}/{}.aar'.format(link, name, version, name_version)
                    self.pom_queue.put(google_link_pom)
                    self.download_queue.put(google_link_jar)
                    self.download_queue.put(google_link_aar)
        else:
            maven_link = "http://repo2.maven.org/maven2/{}/{}/".format(link, name)
            maven_request = requests.get(maven_link).text
            maven_soup = BeautifulSoup(maven_request, 'html.parser')
            version = maven_soup.find_all('a')[1].attrs['href'].replace('/', '')
            last_link = '{}{}/{}-{}'.format(maven_link, version, name, version)
            pom_link = last_link + '.pom'
            aar_link = last_link + '.aar'
            jar_link = last_link + '.jar'
            self.pom_queue.put(pom_link)
            self.download_queue.put(aar_link)
            self.download_queue.put(jar_link)

    def __download(self, url):
        filename = url.rsplit('/',1)[1]

        r = requests.get(url, allow_redirects=True)
        if r.status_code >= 200 and r.status_code <= 299:
            print('downloading: ' + url)
            open(filename, 'wb').write(r.content)

    def download_worker(self):
        while True:
            item = self.download_queue.get()
            if item is None:
                break
            self.__download(item)
            self.download_queue.task_done()
    
    def pom_worker(self):
        while True:
            item = self.pom_queue.get()
            if item is None:
                print('breaking pom worker')
                break

            self.__parse_pom(item)
            self.pom_queue.task_done()

    def version_checker_worker(self):
        while True:
            item = self.version_checking_queue.get()
            if item is None:
                break
            self.__check_version(item)
            self.version_checking_queue.task_done()

    def add_gradle_to_queue(self, path):
        gradle = path.split(":")
        first_path = gradle[0].replace(".", "/")
        pom_file = "{}-{}.pom".format(gradle[1], gradle[2])
        jar_file = "{}-{}.jar".format(gradle[1], gradle[2])
        aar_file = "{}-{}.aar".format(gradle[1], gradle[2])

        google_link = "https://maven.google.com/{}/{}/{}/".format(first_path, gradle[1], gradle[2])
        maven_link = "http://repo2.maven.org/maven2/{}/{}/{}/".format(first_path, gradle[1], gradle[2])
        self.pom_queue.put(google_link + pom_file)
        self.pom_queue.put(maven_link + pom_file)
        self.download_queue.put(google_link + jar_file)
        self.download_queue.put(google_link + aar_file)
        self.download_queue.put(maven_link + jar_file)
        self.download_queue.put(maven_link + aar_file)


    def run(self):
        # html = threading.Thread(target=self.html_parse_worker)
        # html.start()
        pom = threading.Thread(target=self.pom_worker)
        pom.start()
        version = threading.Thread(target=self.version_checker_worker)
        version.start()
        download = threading.Thread(target=self.download_worker)
        download.start()
        download.join()



if __name__ == '__main__':
    dd = DependencyDownloader()
    dd.add_gradle_to_queue('android.arch.persistence.room:compiler:1.0.0-alpha9')
    dd.add_gradle_to_queue('android.arch.persistence.room:rxjava2:1.0.0-alpha9')
    dd.add_gradle_to_queue('android.arch.persistence.room:runtime:1.0.0-alpha9')
    dd.add_gradle_to_queue('com.squareup.picasso:picasso:2.5.2')
    dd.add_gradle_to_queue('com.squareup.retrofit2:converter-gson:2.3.0')
    dd.add_gradle_to_queue('com.squareup.retrofit2:retrofit:2.3.0')
    dd.add_gradle_to_queue('io.reactivex.rxjava2:rxjava:2.1.0')
    dd.add_gradle_to_queue('io.reactivex.rxjava2:rxandroid:2.0.1')
    dd.add_gradle_to_queue('com.google.code.gson:gson:2.8.0')
    dd.add_gradle_to_queue('com.android.support:appcompat-v7:26.0.1')
    dd.run()



