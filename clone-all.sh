#! /usr/bin/sh

## Usage: clone-all.sh will clone of of your chimes-related bitbucket repos (except for chimes_lsq)
##        into the imports directory. Prior to using this script you need to fork all
##        of the repos for chimes in your personal bitbucket space.


## BITBUCKET_USER should be your LLNL OUN.  Set in your .profile.  
if [ -z "$BITBUCKET_USER" ] ; then 
	echo "Enter your LLNL OUN"
	read BITBUCKET_USER
fi

if [ ! -d "imports" ] ; then
	 mkdir imports
fi

cd imports

CHIMES_REPOS="al_driver chimes_calculator chimes_developer_notes chimes_git_guide dlars owlqn"
for repo in $CHIMES_REPOS ; do
	 if [ ! -d $repo ] ; then
		  git clone ssh://git@mybitbucket.llnl.gov:7999/~$BITBUCKET_USER/$repo.git $repo
        if [ $? -ne 0 ] ; then																													  
				echo 'git clone failed'
				exit
		  fi
	 else
		  echo "$repo already found in imports. Not cloning"
	 fi
done
cd -
