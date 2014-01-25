from mega import Mega
import mega.errors
from datetime import datetime
import time
import sys
import os.path
import os

class MegaFile:
    def __init__(self, node, allfiles = None):
        self.node = node
        self.allfiles = allfiles

    def name(self):
        return self.node['a']['n']

    def isDir(self):
        # no size, means a dir 
        return not 's' in self.node

    def size(self):
        return self.node['s']

    def id(self):
        return self.node['h']

    def parent(self):
        p = self.node['p']
        if p == "":
            return None
        else:
            return MegaFile(self.allfiles[p], self.allfiles)

    def __str__(self):
        ret = self.name()
        p = self.parent()
        if p != None:
            ret = str(p) + ret
        
        if self.isDir():
            ret += "/"
        return ret

def ls(files):
    for f in files.values():
        print str(MegaFile(f, files)) #+ "\t%s" % (f)

def resolve_leaf_id(files, path):
    parent = None
    """Find root"""
    for f in files.values():
        if f['t'] == 2:
            parent = f
            break
    if parent == None:
        raise KeyError("No root")
    if path == "":
        return parent
    for component in path.split("/"):
        child = None
        for f in files.values():
            if f['p'] == parent['h'] and f['a']['n'] == component:
                child = f
                break
        if child == None:
            str = "Can't find %s under %s" % (component, parent['a']['n'])
            raise KeyError(str)
        #print "child=%s" % component
        parent = child
    return parent

class MegaUploader:
    def __init__(self, username, password, files = None):
        self._files = files
        self._m = None
        self._u = username
        self._p = password

    def m(self):
        if self._m != None:
            return self._m
        self._m = Mega().login(self._u, self._p)
        return self._m

    def files(self):
        if self._files != None:
            return self._files
        sleep = 1
        self._files = self.m().get_files()
        #print self._files
        return self._files
        
    def upload(self, fs_filename, size):
        start = datetime.now()
        dirname = fs_filename
        todo_mkdir = []
        while True:
            try:
                dir_entry = resolve_leaf_id(self.files(), dirname)
                dir_id = dir_entry['h']
                #if the file already exists...todo_mkdir hasn't been filed yet and dirname == filename
                if len(todo_mkdir) == 0:
                    file_id = dir_id
                    mfile = MegaFile(dir_entry)
                    if mfile.size() != size:
                        raise Exception("Uploaded size(%d) doesn't match outgoing size(%d)" % (mfile.size(), size))
                    print "%s is already uploaded as a file, size matches" % fs_filename
                    return file_id
                # if we got here part of the directory exists
                break
            except KeyError as ke:
                print ke.message
                todo_mkdir.append(os.path.basename(dirname))
                dirname = os.path.dirname(dirname)
        filename = todo_mkdir[0]
        todo_mkdir = todo_mkdir[1:]
        #print ["dir_id", dir_id]
        for dirpart in reversed(todo_mkdir):
            #print "mkdir "+dirpart
            ret = self.m().create_folder(dirpart, dir_id)
            dir_entry = ret['f'][0]
            dir_id = dir_entry['h']
            self._files = None

        sleep_delay = 1
        while True:
            try:
                ret = self.m().upload(fs_filename, dest=dir_id)
                break
            except mega.errors.RequestError as re:
                print ['Exception during upload', re]
                print "Sleeping for %d seconds before trying again" % sleep_delay
                time.sleep(sleep_delay)
                sleep_delay = sleep_delay * 2
        delta = (datetime.now() - start)
        ms = delta.seconds * 1000 + delta.microseconds/1000
        if ms != 0:
            print str(1000.0*size/1024/1024/ms) + "MB/s %dbytes in %sseconds %s" % (size, ms/1000, fname)


if __name__ == '__main__':
    [config, path] = sys.argv[1:]
    [user, password] = open(config).read().strip().split(" ")
    mu = MegaUploader(user, password)
    for root, dirs, files in os.walk(path):
        for name in files:
            fname = os.path.join(root, name)
            if fname[:2] == "./":
                fname = fname[2:]
            if os.path.isfile(fname):
                bytes_read = os.stat(fname).st_size
                if bytes_read == 0:
                    continue
                mu.upload(fname, bytes_read)
