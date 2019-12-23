#!/usr/bin/python

#****************************************************************************
#* ivpm.py
#* 
#* This is the bootstrap ivpm.py script that is included with each project.
#* This script ensures that the *actual* ivpm is downloaded in the 
#* project packages dir
#****************************************************************************
import os.path
import sys
import subprocess

#********************************************************************
#* download_ivpm
#*
#* 
#********************************************************************
def download_ivpm(packages_dir):
    if os.path.isdir(packages_dir) == False:
        os.makedirs(packages_dir)
       
    cwd = os.getcwd()
    os.chdir(packages_dir)
    status = os.system("git clone https://github.com/mballance/ivpm.git")
    os.chdir(cwd);

def main():
    scripts_dir = os.path.dirname(os.path.realpath(__file__))
    project_dir = os.path.dirname(scripts_dir)
    packages_dir = project_dir + "/packages"
    ivpm_dir = packages_dir + "/ivpm"
    
    help_requested = False;
    
    for arg in sys.argv:
        if (arg == "-help" or arg == "--help" 
            or arg == "-h" or arg == "--h" 
            or arg == "-?"):
            help_requested = True
            
    
    # First see if we've already downloaded IVPM
    if os.path.isdir(ivpm_dir) == False:
        if (help_requested):
            print "Local help";
            sys.exit(1);
        download_ivpm(packages_dir)
        
    # Bring in the actual IVPM script and call it
    sys.path.insert(0, ivpm_dir + "/scripts")
    import ivpm
    ivpm.ivpm_main(project_dir, sys.argv)
    
if __name__ == "__main__":
    main()
