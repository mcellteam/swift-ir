# SWiFT-IR Development

## Joint GIT-based development without a shared repository

The following instructions assume:

 * The project working directory will be: /home/me/code/swift_proj

 * The file containing the GIT bundle is named: swift.bundle


## Setting up a NEW GIT Repository from a GIT Bundle
```
Put the new GIT bundle file (swift.bundle) into the directory above your working directory.

So if you plan for your source files to be in:

   /home/me/code/swift_proj

Then place the "swift.bundle" file at:

   /home/me/code/swift.bundle

Then cd to the directory containing the bundle:

   $ cd /home/me/code

Now clone the repository from the "swift.bundle" file into the "swift_proj" directory:

   $ git clone swift.bundle swift_proj

Go to the newly cloned project directory:

   $ cd /home/me/code/swift_proj

Now check out the files:

   $ git checkout master

Tag the current commit as the "shared" position:

   $ git tag -f shared

Edit the /home/me/code/swift_proj/.git/config file to remove everything but the [core] section:

    [core]
	    repositoryformatversion = 0
	    filemode = true
	    bare = false
	    logallrefupdates = true
    [remote "origin"]
	    url = /home/me/code/swift.bundle
	    fetch = +refs/heads/*:refs/remotes/origin/*
    [branch "master"]
	    remote = origin
	    merge = refs/heads/master

The final version should look like this:

    [core]
	    repositoryformatversion = 0
	    filemode = true
	    bare = false
	    logallrefupdates = true
```



## Normal Work Flow
```
Work in the project directory: /home/me/code/swift_proj

Change files, add files, delete files, commit files.
```



## Send Updates via a GIT Bundle
```
Be sure that everything is committed before creating a GIT bundle.

Change directory to the project directory:

   $ cd /home/me/code/swift_proj

Create a GIT bundle with the commits between the "shared" position and "master":

   $ git bundle create ../swift.bundle shared..master

Send the file "swift.bundle" to the other team members.
```



## Get Updates from a GIT Bundle
```
Put the updated GIT bundle file in /home/me/code/swift.bundle

Change directory to the project directory:

   $ cd /home/me/code/swift_proj

Pull the files from the GIT bundle:

   $ git pull ../swift.bundle master

Checkout the current master branch:

   $ git checkout master

Tag the current commit as the new "shared" position:

   $ git tag -f shared

```

