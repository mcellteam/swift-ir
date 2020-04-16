# SWiFT-IR Development

## Finding Commit ID from Source Hash

Modern versions of alignem.py and alignem_swift.py will show a "Source Hash"
field in the lower right corner of the main window. This can be used to get
the GIT commit ID (GIT hash) of that version. This is best explained with
an example ...

Suppose the Source Hash shown is: bd63e14fd7a45d2949ca5fdd27f7ed87c1ef4905

You will want to search the GIT repository for the version of "source_info.py" 
that contains that hash string. This can be done with GIT's "search" option
(-S) as follows:

```
$ git log -S'bd63e14fd7' -- source_info.json
```

Note that you don't need to specify the full hash. Also note that you need
to specify the file to be searched ("source_info.json") after the "--". This
command will show the commit messages associated with that value in the
file "source_info.json". In this example:

```
$ git log -S'bd63e14fd7' -- source_info.json

commit 14370af4fa0346e23f6f5c2c1163e41ca08f24c1
Author: Bob Kuczewski <bobkuczewski@salk.edu>
Date:   Wed Apr 8 21:56:29 2020 -0700

    Implementing the poly_order field as a per-scale item.
    
    Note that the other 2 per-scale flags don't seem to retain their
    values between scale changes in this version.

commit 1af1de55315ad93f2529107991a0d95dc7547287
Author: Bob Kuczewski <bobkuczewski@salk.edu>
Date:   Wed Apr 8 18:18:05 2020 -0700

    Added poly_order to the data model at each scale (defaults to 4).
    
    This commit just adds "poly_order" to the data model and doesn't yet
    connect it to the field in the GUI.
```

This shows the two commits associated with that Source Hash. It's not clear
why there are two. It's possible that they both make reference to the same
change (diff) in the repository. In general, the second commit will be the one
that matches the Source Hash:

```
$ git checkout 1af1de55
Note: switching to '1af1de55'.
 :
 :
HEAD is now at 1af1de5 Added poly_order to the data model at each scale (defaults to 4).
```

At this point, you can verify that this is the proper commit by checking the
current Source Hash in that commit:

```
$ cat source_info.json

{
  "current_hash": "bd63e14fd7a45d2949ca5fdd27f7ed87c1ef4905",
  "tagged_versions": {
    "2eac19472e2631173bbbe09d3c4251e219508602": "0.2.2",
    "5d9fc94902a283bf458d7be61f6dccaafd5fb553": "0.2.1"
  }
}
```

Since the "current_hash" field matches the desired "Source Hash", this is most
likely the version that reported the original "Source Hash" value. The phrase
"most likely" is appropriate because this mechanism depends on developers actually
running their code before making the commit. It is the running "alignem.py"
program that stores the current hash value into "source_info.py". If "alignem.py"
wasn't run before making the commit, then the hash value may not be in the file.

Note that additional options can be passed to the git log function. For example,
the "--oneline" option can be used to get simplified output:

```
$ git log -S'bd63e14fd7' --oneline -- source_info.json
14370af Implementing the poly_order field as a per-scale item.
1af1de5 Added poly_order to the data model at each scale (defaults to 4).
```

GIT also supports many other formatting options such as "--pretty=format":

```
$ git log -S'bd63e14fd7' --pretty=format:"%h %cn on %ad ==> %s" -- source_info.json
14370af Bob Kuczewski on Wed Apr 8 21:56:29 2020 -0700 ==> Implementing the poly_order field as a per-scale item.
1af1de5 Bob Kuczewski on Wed Apr 8 18:18:05 2020 -0700 ==> Added poly_order to the data model at each scale (defaults to 4).
```


## Resolving Conflicts in the "source_info.json" File

The "**source_info.json**" file maintains a current hash of all the source
code files in the project. It also retains a history of tagged versions
and their corresponding hash values. This information is valuable for
historical reasons, but it is also useful for displaying and comparing
the current source code to known versions.

The "**source_info.json**" file is automatically updated by **alignem.py** or
**alignem_swift.py** whenever it differs from the current source code. This
makes it very easy (almost trivial) to keep it maintained during the
development process. All that's needed is to run the code (either
**alignem.py** or **alignem_swift.py**) so that it updates the file as needed.
It is expected that this would happen before every commit since code
should NOT be committed if it hasn't been run at least once.

The only somewhat serious problem with this approach arises when the
code needs to be merged. In almost any merge scenario, the hash values
stored in "**source_info.json**" will be different, and GIT will not know
which version to use. So GIT will modify the file to insert its own
"merge markers" as shown in this example:

```
{
<<<<<<< HEAD
  "current_hash": "052f4245058a8f4f84886d27cb1c096f7ca2e483",
=======
  "current_hash": "03f477aebda2d6656ae6ea911fa5ee98278fdd72",
>>>>>>> d8df7c5d9d97a774787d8ca4d3d089ce73ed0098
  "tagged_versions": {
    "150e0acd86a3c57a7d79fde4b3c4e225b55f26e4": "0.2.3",
    "2eac19472e2631173bbbe09d3c4251e219508602": "0.2.2",
    "5d9fc94902a283bf458d7be61f6dccaafd5fb553": "0.2.1"
  }
}
```

This means that the file would need to be edited by hand every time a
merge was done to either choose one of the "current_hash" values or to
delete them both so they will be automatically regenerated.

In order to avoid this manual work for every merge, the **alignem.py** and
**alignem_swift.py** programs will automatically fix this whenever they are
run. Rather than importing the file directly as JSON (which would fail
with those markers present), they first read the file and check it for
GIT merge markers. If they are found, then they are removed and a new
"current_hash" is calculated and written to the file. This generally
happens just by running either **alignem.py** or **alignem_swift.py**.

Of course, this cannot resolve other merge conflicts that might be found.
They must be resolved by hand just as they always have. But when the only
remaining merge conflict involves "**source_info.json**", it can generally
be resolved by simply running **alignem.py** or **alignem_swift.py**. No project
needs to be opened, and nothing else needs to be done inside the application.
Just run it and exit. That will update the "**source_info.json**" file. If there
are no other merge conflicts (or if they've been resolved by hand), then the
new merge can be committed using the standard process.

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

