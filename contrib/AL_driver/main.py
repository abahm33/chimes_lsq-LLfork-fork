# Global (python) modules

import os
import sys

# Local modules

import helpers
import gen_ff
import run_md
import cluster
import gen_selections
import vasp_driver
import restart

# Allow config file to be read from local directory

local_path = os.path.normpath(helpers.run_bash_cmnd("pwd").rstrip())
sys.path.append(local_path)
import config  # User-specified "global" vars


def main(args):

	""" 
	
	Code Author: Rebecca K Lindsey (RKL) - 2019

	Active Learning Driver Main.

	Usage: unbuffer python ../PYTHON_DRIVER/main.py 0 1 2 | tee driver.log 

	Notes: 

	       - Run location is specified in the config file (WORKING_DIR), NOT the 
	
	       - This tool works most effectively when run with screen during remote runs
	         (screen allows the session to be detached/reattached)	
	
	       - Build documentation with: ./build_docs.sh 
	         ...This will create .html files in the doc directory that can be opened
		 with any browser (i.e. firefox, if running on the LC)	
	
	       - Second argument to main.py is a list of cycles to run (i.e. ALC-0, ALC-, ALC-2)
	         ... This must ALWAYS be a sequence starting from 0
		 
	       - Consider A-mat load balancing: some frames can be much smaller than others
	              
	WARNING: Assumes lsq2.py is using the ***hardcoded*** DLARS path
	
	WARNING: Ensure all queued jobs have ended or been killed before restarting      

	WARNING: FIRST/FIRSTALL untested

	WARNING: AL does not (yet) support different stress/energy options for different cases

	WARNING: This driver does NOT support SPLITFI functionality.

	WARNING: DLARS/DLASSO is NOT supported with split files.	
	
	WARNING: Per-atom energies will be incorrect if number of atoms for multiple types is 
	         identical across the entire A-mat (i.e. for a CO system) ... This can be/is
		 rectified by running additional AL cycles that extracts individual molecules
		 
	To Do: 
	
	       - Add ability to do full-frame ALC only (no clustering) ... this would require
		 either the ability to start at ALC-1, or the ability to run MD for ALC-0
	
	       - Add a utility to check/fix data types set in config
	
	       - Create support for stress inclusion/weighting	       
	       
	       - Introduce a test suite	
	
	       - Create support for restarted DLARS/DLASSO jobs
	       
	       - Create support for distributed DLARS/DLASSO jobs
	       	
	       - Consider A-mat load balancing: some frames can be much smaller than others	
	       
	       - Add an ability to go back and run additional independent simulations for various ALC's/cases
	       
	       - Build a test suite		 

		
	"""	       
		


	################################
	# Initialize vars
	################################

	THIS_CASE  = 0
	THIS_INDEP = 0
	EMAIL_ADD  = '' 
	
	if os.path.normpath(config.WORKING_DIR) != local_path:
	
		print "Error: this script was not run from config.WORKING_DIR!"
		print "Exiting."
		
		exit()
	
	print "The following has been set as the working directory:"
	print '\t', config.WORKING_DIR
	print "The ALC-X contents of this directory will be overwritten."

	################################
	# Pre-process user specified variables
	################################

	config.ATOM_TYPES.sort()

	config.CHIMES_SOLVER  = config.HPC_PYTHON + " " + config.CHIMES_SOLVER
	config.CHIMES_POSTPRC = config.HPC_PYTHON + " " + config.CHIMES_POSTPRC

	config.VASP_POSTPRC   = config.HPC_PYTHON + " " + config.VASP_POSTPRC
	
	if config.EMAIL_ADD:
		EMAIL_ADD = config.EMAIL_ADD	

	################################
	################################
	# Begin Active Learning
	################################
	################################

	print "Will run for the following active learning cycles:"

	ALC_LIST = args

	for THIS_ALC in ALC_LIST:
		print THIS_ALC
		

	# Set up the restart file
		
	restart_controller = restart.restart() # Reads/creates restart file. Must be named "restart.dat"

	ALC_LIST = restart_controller.update_ALC_list(ALC_LIST)

	print "After processing restart file, will run for the following active learning cycles:"

	for THIS_ALC in ALC_LIST:
		print THIS_ALC


	for THIS_ALC in ALC_LIST:

		THIS_ALC = int(THIS_ALC)
		
		
		# Let the ALC process know whether this is a restarted cycle or a completely new cycle
		
		if THIS_ALC != restart_controller.last_ALC:
		
			restart_controller.reinit_vars()
		
		
		# Prepare the restart file

		restart_controller.update_file("ALC: " + str(THIS_ALC) + '\n')
			

		print "Working on ALC:", THIS_ALC

		os.chdir(config.WORKING_DIR)
		

		# Begins in the working directory (WORKING_DIR)

		if THIS_ALC == 0: # Then this is the first ALC, so we need to do things a bit differently ... 
		
		
			if not restart_controller.BUILD_AMAT: # Then we haven't even begun this ALC

				# Set up/move into the ALC directory
			
				helpers.run_bash_cmnd("rm -rf ALC-" + str(THIS_ALC))
				helpers.run_bash_cmnd("mkdir  ALC-" + str(THIS_ALC))
			
			os.chdir("ALC-" + str(THIS_ALC))
			
					
			################################
			# Generate the force field	
			################################
			
			if not restart_controller.BUILD_AMAT:
			
				active_job = gen_ff.build_amat(THIS_ALC,
						prev_gen_path      = config.ALC0_FILES,
						job_email          = config.HPC_EMAIL,
						job_ppn            = str(config.HPC_PPN),
						job_nodes          = config.CHIMES_BUILD_NODES,
						job_walltime       = config.CHIMES_BUILD_TIME,	
						job_queue          = config.CHIMES_BUILD_QUEUE,		
						job_account        = config.HPC_ACCOUNT, 
						job_system         = config.HPC_SYSTEM,
						job_executable     = config.CHIMES_LSQ)
						
				helpers.wait_for_job(active_job, job_system = config.HPC_SYSTEM, verbose = True, job_name = "build_amat")

				restart_controller.update_file("BUILD_AMAT: COMPLETE" + '\n')
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "BUILD_AMAT: COMPLETE ")	
			else:
				restart_controller.update_file("BUILD_AMAT: COMPLETE" + '\n')
				
			
			if not restart_controller.SOLVE_AMAT:
			
				active_job = gen_ff.solve_amat(THIS_ALC, 
						weights_force  = config.WEIGHTS_FORCE,
						weights_energy = config.WEIGHTS_ENER,
						regression_alg = config.REGRESS_ALG,
						regression_var = config.REGRESS_VAR,
						job_email      = config.HPC_EMAIL,
						job_ppn        = str(config.HPC_PPN),
						job_nodes      = config.CHIMES_SOLVE_NODES,
						job_walltime   = config.CHIMES_SOLVE_TIME,	
						job_queue      = config.CHIMES_SOLVE_QUEUE,					
						job_account    = config.HPC_ACCOUNT, 
						job_system     = config.HPC_SYSTEM,
						job_executable = config.CHIMES_SOLVER)	
						
				helpers.wait_for_job(active_job, job_system = config.HPC_SYSTEM, verbose = True, job_name = "solve_amat")
				
				helpers.run_bash_cmnd(config.CHIMES_POSTPRC + " GEN_FF/params.txt")
			
				restart_controller.update_file("SOLVE_AMAT: COMPLETE" + '\n')	
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "SOLVE_AMAT: COMPLETE ")
			
			else:
				restart_controller.update_file("SOLVE_AMAT: COMPLETE" + '\n')	
			
			
			
			################################				
			# Extract/process/select clusters
			################################
			
			if not restart_controller.CLUSTER_EXTRACTION:

				# Get a list of files from which to extract clusters
			
				traj_files = helpers.cat_to_var("GEN_FF/traj_list.dat")[1:]
			
			
				# Extract clusters from each file, save into own repo, list
			
				cat_xyzlist_cmnd    = ""
				cat_ts_xyzlist_cmnd = ""
			
			
				for i in xrange(len(traj_files)):
			
					# Pre-process name
					
					traj_files[i] = traj_files[i].split()[1]
					
					print "Extracting clusters from file: ", traj_files[i]
					
					# Extract
			
					cluster.generate_clusters(
								traj_file   = "GEN_FF/" + traj_files[i].split()[0],
								tight_crit  = config.TIGHT_CRIT,
								loose_crit  = config.LOOSE_CRIT,
								clu_code    = config.CLU_CODE,
								compilation = "g++ -std=c++11 -O3")
					
					repo = "CFG_REPO-" + traj_files[i].split()[0]
					
					helpers.run_bash_cmnd("mv CFG_REPO " + repo)
					
					# list
			
					cluster.list_clusters(repo, 
								config.ATOM_TYPES)
										
					helpers.run_bash_cmnd("mv xyzlist.dat    " + traj_files[i].split()[0] + ".xyzlist.dat"   )
					helpers.run_bash_cmnd("mv ts_xyzlist.dat " + traj_files[i].split()[0] + ".ts_xyzlist.dat")
					
					cat_xyzlist_cmnd    += traj_files[i].split()[0] + ".xyzlist.dat "
					cat_ts_xyzlist_cmnd += traj_files[i].split()[0] + ".ts_xyzlist.dat "
					
				helpers.cat_specific("xyzlist.dat"   , cat_xyzlist_cmnd   .split())
				helpers.cat_specific("ts_xyzlist.dat", cat_ts_xyzlist_cmnd.split())

				helpers.run_bash_cmnd("rm -f " + cat_xyzlist_cmnd   )
				helpers.run_bash_cmnd("rm -f " + cat_ts_xyzlist_cmnd)
				
				restart_controller.update_file("CLUSTER_EXTRACTION: COMPLETE" + '\n')
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "CLUSTER_EXTRACTION: COMPLETE ")

			else:
				restart_controller.update_file("CLUSTER_EXTRACTION: COMPLETE" + '\n')
			
			if not restart_controller.CLUENER_CALC:

				# Compute cluster energies
			
				active_jobs = cluster.get_repo_energies(
						base_runfile   = config.ALC0_FILES + "/run_md.base",
						driver_dir     = config.DRIVER_DIR,
						job_email      = config.HPC_EMAIL,
						job_ppn        = str(config.HPC_PPN),
						job_walltime   = "1",					
						job_account    = config.HPC_ACCOUNT, 
						job_system     = config.HPC_SYSTEM,
						job_executable = config.CHIMES_MD)	
						
				helpers.wait_for_jobs(active_jobs, job_system = config.HPC_SYSTEM, verbose = True, job_name = "get_repo_energies")
			
				print helpers.run_bash_cmnd("pwd")
				print helpers.run_bash_cmnd("ls -lrt")	
			
				restart_controller.update_file("CLUENER_CALC: COMPLETE" + '\n')	
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "CLUENER_CALC: COMPLETE ")
				
			else:
				restart_controller.update_file("CLUENER_CALC: COMPLETE" + '\n')	
			
			
			if not restart_controller.CLU_SELECTION:
			
				# Generate cluster sub-selection and store in central repository
			
				gen_selections.cleanup_repo(THIS_ALC)
			
				gen_selections.gen_subset(
						nsel     = config.MEM_NSEL, # Number of selections to make    
						nsweep   = config.MEM_CYCL, # Number of MC sqeeps	      
						nbins    = config.MEM_BINS, # Number of histogram bins  	
						ecut     = config.MEM_ECUT, # Maximum energy to consider
						seed     = config.SEED    ) # Seed for random number generator	
			
				gen_selections.populate_repo(THIS_ALC)

				repo = "CASE-" + str(THIS_CASE) + "_INDEP_" + str(THIS_INDEP) + "/CFG_REPO/"
				
				restart_controller.update_file("CLU_SELECTION: COMPLETE" + '\n')
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "CLU_SELECTION: COMPLETE ")
				
			else:
				restart_controller.update_file("CLU_SELECTION: COMPLETE" + '\n')

			
			################################
			# Launch VASP
			################################
			
			if not restart_controller.CLEANSETUP_VASP:
			
				vasp_driver.cleanup_and_setup(["all"], build_dir=".")
			
				restart_controller.update_file("CLEANSETUP_VASP: COMPLETE" + '\n')
				
			else:
				restart_controller.update_file("CLEANSETUP_VASP: COMPLETE" + '\n')
			
			
			if not restart_controller.INIT_VASPJOB:	
	
				vasp_driver.cleanup_and_setup(["all"], build_dir=".") # Always clean up, just in case	

				active_job = vasp_driver.setup_vasp(THIS_ALC,
						["all"], 
						config.ATOM_TYPES,
						THIS_CASE, 
						config.THIS_SMEAR,
						first_run      = True,
						basefile_dir   = config.VASP_FILES,
						vasp_exe       = config.VASP_EXE,
						job_email      = config.HPC_EMAIL,
						job_nodes      = config.VASP_NODES,
						job_ppn        = config.HPC_PPN,
						job_walltime   = config.VASP_TIME,
						job_queue      = config.VASP_QUEUE,
						job_account    = config.HPC_ACCOUNT, 
						job_system     = config.HPC_SYSTEM)
						# Not using this option anymore:
						#traj_list      = config.ALC0_FILES + "/traj_list.dat", # Has a temperature for each file ... expected as integer

				helpers.wait_for_job(active_job[0], job_system = config.HPC_SYSTEM, verbose = True, job_name = "setup_vasp")

				restart_controller.update_file("INIT_VASPJOB: COMPLETE" + '\n')	
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "INIT_VASPJOB: COMPLETE ")		
				
			else:
				restart_controller.update_file("INIT_VASPJOB: COMPLETE" + '\n')
			
			# Check that the job was complete
			
			if not restart_controller.ALL_VASPJOBS:

				while True:

					active_jobs = vasp_driver.continue_job(
							["all"], 
							job_system     = config.HPC_SYSTEM)
							
					print "active jobs: ", active_jobs			
							
					if len(active_jobs) > 0:
				
						print "waiting for restarted vasp job."
				
						helpers.wait_for_jobs(active_jobs, job_system = config.HPC_SYSTEM, verbose = True, job_name = "setup_vasp - restarts")
					else:
						print "All jobs are complete"
						break		
			
			
				restart_controller.update_file("ALL_VASPJOBS: COMPLETE" + '\n')
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "ALL_VASPJOBS: COMPLETE ")
				
			else:
				restart_controller.update_file("ALL_VASPJOBS: COMPLETE" + '\n')
				
			if not restart_controller.THIS_ALC:

				# Post-process the vasp jobs
			
				print "post-processing..."	
			
				vasp_driver.post_process(["all"], "ENERGY",
					vasp_postproc = config.VASP_POSTPRC)

			os.chdir("..")
			
			print "ALC-", THIS_ALC, "is complete"	
			
			restart_controller.update_file("THIS_ALC: COMPLETE" + '\n')
			
			helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "THIS_ALC: COMPLETE ")		
			
		else:
		
			if not restart_controller.BUILD_AMAT: # Then we haven't even begun this ALC

				# Set up/move into the ALC directory
			
				helpers.run_bash_cmnd("rm -rf ALC-" + str(THIS_ALC))
				helpers.run_bash_cmnd("mkdir  ALC-" + str(THIS_ALC))
			
			os.chdir("ALC-" + str(THIS_ALC))
			
			vasp_all_path = config.WORKING_DIR + "/ALC-" + `THIS_ALC-1` + "/VASP-all/"
			vasp_20F_path = ""
			
			if THIS_ALC > 1:
				vasp_20F_path = config.WORKING_DIR + "/ALC-" + `THIS_ALC-1` + "/VASP-20/"
				
			if not restart_controller.BUILD_AMAT:
			
				active_job = gen_ff.build_amat(THIS_ALC, 
					prev_vasp_all_path = vasp_all_path,
					prev_vasp_20_path  = vasp_20F_path,
					job_email          = config.HPC_EMAIL,
					job_ppn            = str(config.HPC_PPN),
					job_nodes          = config.CHIMES_BUILD_NODES,
					job_walltime       = config.CHIMES_BUILD_TIME,	
					job_queue          = config.CHIMES_BUILD_QUEUE,						
					job_account        = config.HPC_ACCOUNT, 
					job_system         = config.HPC_SYSTEM,
					job_executable     = config.CHIMES_LSQ)
			
				helpers.wait_for_job(active_job, job_system = config.HPC_SYSTEM, verbose = True, job_name = "build_amat")
			
				restart_controller.update_file("BUILD_AMAT: COMPLETE" + '\n')
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "BUILD_AMAT: COMPLETE ")
			else:
				restart_controller.update_file("BUILD_AMAT: COMPLETE" + '\n')
						
				
			if not restart_controller.SOLVE_AMAT:	
			
				active_job = gen_ff.solve_amat(THIS_ALC, 
					weights_force  = config.WEIGHTS_FORCE,
					weights_energy = config.WEIGHTS_ENER,
					regression_alg = config.REGRESS_ALG,
					regression_var = config.REGRESS_VAR,	
					job_email      = config.HPC_EMAIL,					
					job_ppn        = str(config.HPC_PPN),
					job_nodes      = config.CHIMES_SOLVE_NODES,
					job_walltime   = config.CHIMES_SOLVE_TIME,	
					job_queue      = config.CHIMES_SOLVE_QUEUE,								
					job_account    = config.HPC_ACCOUNT, 
					job_system     = config.HPC_SYSTEM,
					job_executable = config.CHIMES_SOLVER)	
					
				helpers.wait_for_job(active_job, job_system = config.HPC_SYSTEM, verbose = True, job_name = "solve_amat")	

				helpers.run_bash_cmnd(config.CHIMES_POSTPRC + " GEN_FF/params.txt")
				
				restart_controller.update_file("SOLVE_AMAT: COMPLETE" + '\n')	
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "SOLVE_AMAT: COMPLETE ")
			else:
				restart_controller.update_file("SOLVE_AMAT: COMPLETE" + '\n')	
			
			################################				
			# Run MD
			################################
			
			
			# ... May want to consider making speciation optional ... can add another key word that allows the user to set up different 
			#    types of post-processing jobs
			
			
			if not restart_controller.RUN_MD:
					
				# Run the MD/cluster jobs
			
				active_jobs = []
				
				#print "running for cases:", config.NO_CASES
			
				for THIS_CASE in xrange(config.NO_CASES):

					active_job = run_md.run_md(THIS_ALC, THIS_CASE, THIS_INDEP,
						basefile_dir   = config.CHIMES_MDFILES, 
						driver_dir     = config.DRIVER_DIR,
						penalty_pref   = 1.0E6,		
						penalty_dist   = 0.02, 		
						job_name       = "ALC-"+ str(THIS_ALC) +"-md-c" + str(THIS_CASE) +"-i" + str(THIS_INDEP),
						job_email      = config.HPC_EMAIL,	   	 
						job_ppn        = config.HPC_PPN,	   	 
						job_nodes      = config.CHIMES_MD_NODES,
						job_walltime   = config.CHIMES_MD_TIME,      
						job_queue      = config.CHIMES_MD_QUEUE,      
						job_account    = config.HPC_ACCOUNT, 
						job_executable = config.CHIMES_MD,	 
						job_system     = "slurm",  	 
						job_file       = "run.cmd")
		
					active_jobs.append(active_job.split()[0])	
									
				helpers.wait_for_jobs(active_jobs, job_system = config.HPC_SYSTEM, verbose = True, job_name = "run_md")

				restart_controller.update_file("RUN_MD: COMPLETE" + '\n')
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "RUN_MD: COMPLETE ")
			else:
				restart_controller.update_file("RUN_MD: COMPLETE" + '\n')
						
			if not restart_controller.POST_PROC:
			
				for THIS_CASE in xrange(config.NO_CASES):	
			
					# Post-process the MD job
			
					run_md.post_proc(THIS_ALC, THIS_CASE, THIS_INDEP,
						"C1 O1 1(O-C)",
						"C1 O2 2(O-C)",
						"C2 O2 1(C-C) 2(O-C)",
						"C3 O2 2(C-C) 2(O-C)",
						basefile_dir   = config.CHIMES_MDFILES, 
						driver_dir     = config.DRIVER_DIR,
						penalty_pref   = config.CHIMES_PEN_PREFAC,	  
						penalty_dist   = config.CHIMES_PEN_DIST,		  
						molanal_dir    = config.CHIMES_MOLANAL, 
						local_python   = config.HPC_PYTHON, 	
						do_cluster     = config.DO_CLUSTER,	
						tight_crit     = config.TIGHT_CRIT,	
						loose_crit     = config.LOOSE_CRIT,	
						clu_code       = config.CLU_CODE,  	
						compilation    = "g++ -std=c++11 -O3")

				restart_controller.update_file("POST_PROC: COMPLETE" + '\n')
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "POST_PROC: COMPLETE ")
			else:
				restart_controller.update_file("POST_PROC: COMPLETE" + '\n')	
			
			if not restart_controller.CLUSTER_EXTRACTION:
			
				# list ... remember, we only do clustering/active learning on a single indep (0)
			
				cat_xyzlist_cmnd    = ""
				cat_ts_xyzlist_cmnd = ""		
			
				for THIS_CASE in xrange(config.NO_CASES):
				        
				        repo = "CASE-" + str(THIS_CASE) + "_INDEP_" + str(THIS_INDEP) + "/CFG_REPO/"
				        
				        cluster.list_clusters(repo, 
				        		config.ATOM_TYPES)	
				        		
				        helpers.run_bash_cmnd("mv xyzlist.dat	 " + "CASE-" + str(THIS_CASE) + ".xyzlist.dat"   )
				        helpers.run_bash_cmnd("mv ts_xyzlist.dat " + "CASE-" + str(THIS_CASE) + ".ts_xyzlist.dat")
				        
				        cat_xyzlist_cmnd    += "CASE-" + str(THIS_CASE) + ".xyzlist.dat "
				        cat_ts_xyzlist_cmnd += "CASE-" + str(THIS_CASE) + ".ts_xyzlist.dat "
				        
				helpers.cat_specific("xyzlist.dat"   , cat_xyzlist_cmnd   .split())
				helpers.cat_specific("ts_xyzlist.dat", cat_ts_xyzlist_cmnd.split())
			
				helpers.run_bash_cmnd("rm -f " + cat_xyzlist_cmnd   )
				helpers.run_bash_cmnd("rm -f " + cat_ts_xyzlist_cmnd)
			
				restart_controller.update_file("CLUSTER_EXTRACTION: COMPLETE" + '\n')	
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "CLUSTER_EXTRACTION: COMPLETE ")				
			else:
				restart_controller.update_file("CLUSTER_EXTRACTION: COMPLETE" + '\n')					
			
					
			if not restart_controller.CLUENER_CALC:
			
				# Compute cluster energies
			
				gen_selections.cleanup_repo(THIS_ALC)	
			
				active_jobs = cluster.get_repo_energies(
						calc_central   = True,
						base_runfile   = config.CHIMES_MDFILES + "/" + "run_md.base",
						driver_dir     = config.DRIVER_DIR,
						job_email      = config.HPC_EMAIL,
						job_ppn        = str(config.HPC_PPN),
						job_queue      = config.CALC_REPO_ENER_QUEUE,
						job_walltime   = str(config.CALC_REPO_ENER_TIME),				  
						job_account    = config.HPC_ACCOUNT, 
						job_system     = config.HPC_SYSTEM,
						job_executable = config.CHIMES_MD)	
						
				helpers.wait_for_jobs(active_jobs, job_system = config.HPC_SYSTEM, verbose = True, job_name = "get_repo_energies")

				restart_controller.update_file("CLUENER_CALC: COMPLETE" + '\n')	
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "CLUENER_CALC: COMPLETE ")	
			else:
				restart_controller.update_file("CLUENER_CALC: COMPLETE" + '\n')	


			if not restart_controller.CLU_SELECTION:

				# Generate cluster sub-selection and store in central repository

				gen_selections.gen_subset(
						 repo	  = "../CENTRAL_REPO/full_repo.energies_normed",
						 nsel	  = config.MEM_NSEL, # Number of selections to make    
						 nsweep   = config.MEM_CYCL, # Number of MC sqeeps	       
						 nbins    = config.MEM_BINS, # Number of histogram bins 	 
						 ecut	  = config.MEM_ECUT) # Maximum energy to consider	
						 
				gen_selections.populate_repo(THIS_ALC)   
						 
				restart_controller.update_file("CLU_SELECTION: COMPLETE" + '\n')
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "CLU_SELECTION: COMPLETE ")
			else:
				restart_controller.update_file("CLU_SELECTION: COMPLETE" + '\n')
								 

			################################
			# Launch VASP
			################################
			
			# Note: If multiple cases are being used, only run clean/setup once!
			
			if not restart_controller.CLEANSETUP_VASP:
			
				vasp_driver.cleanup_and_setup(["20", "all"], build_dir=".")
			
				restart_controller.update_file("CLEANSETUP_VASP: COMPLETE" + '\n')
			else:
				restart_controller.update_file("CLEANSETUP_VASP: COMPLETE" + '\n')
				
						
			if not restart_controller.INIT_VASPJOB:
			
				active_jobs = []
				
				vasp_driver.cleanup_and_setup(["20", "all"], build_dir=".")
			
				for THIS_CASE in xrange(config.NO_CASES):
			
					vasp_driver.cleanup_and_setup(["20", "all"], THIS_CASE, build_dir=".") # Always clean up, just in case
			
					active_job = vasp_driver.setup_vasp(THIS_ALC,
							["20", "all"], 
							config.ATOM_TYPES,
							THIS_CASE, 
							config.THIS_SMEAR,
							basefile_dir   = config.VASP_FILES,
							build_dir      = "..", # Put the VASP-x directories in the ALC-X folder
							vasp_exe       = config.VASP_EXE,
							job_email      = config.HPC_EMAIL,
							job_nodes      = config.VASP_NODES,
							job_ppn        = config.HPC_PPN,
							job_walltime   = config.VASP_TIME,
							job_queue      = config.VASP_QUEUE,
							job_account    = config.HPC_ACCOUNT, 
							job_system     = config.HPC_SYSTEM)
							
					active_jobs += active_job
			
				helpers.wait_for_jobs(active_jobs, job_system = config.HPC_SYSTEM, verbose = True, job_name = "setup_vasp")
			
				restart_controller.update_file("INIT_VASPJOB: COMPLETE" + '\n')
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "INIT_VASPJOB: COMPLETE ")
			else:
				restart_controller.update_file("INIT_VASPJOB: COMPLETE" + '\n')

		
			if not restart_controller.ALL_VASPJOBS:

				while True:	# Check that the job was complete
				
					active_jobs = []
				
					for THIS_CASE in xrange(config.NO_CASES):

						active_job = vasp_driver.continue_job(
								["all","20"], THIS_CASE, 
								job_system     = config.HPC_SYSTEM)
								
						active_jobs += active_job
								
					print "active jobs: ", active_jobs			
								
					if len(active_jobs) > 0:
					
						print "waiting for restarted vasp job."
					
						helpers.wait_for_jobs(active_jobs, job_system = config.HPC_SYSTEM, verbose = True, job_name = "setup_vasp - restarts")
					else:
						print "All jobs are complete"
						break	
						
				restart_controller.update_file("ALL_VASPJOBS: COMPLETE" + '\n')
				
				helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "ALL_VASPJOBS: COMPLETE ")
			else:
				restart_controller.update_file("ALL_VASPJOBS: COMPLETE" + '\n')
				
			
			if not restart_controller.THIS_ALC:

				# Post-process the vasp jobs
			
				print "post-processing..."	
			
				vasp_driver.post_process(["all","20"], "ENERGY", config.NO_CASES,
						vasp_postproc = config.VASP_POSTPRC)
						
						
			os.chdir("..")
			
			print "ALC-", THIS_ALC, "is complete"	
			
			restart_controller.update_file("THIS_ALC: COMPLETE" + '\n')	

			print helpers.email_user(config.DRIVER_DIR, EMAIL_ADD, "ALC-" + str(THIS_ALC) + " status: " + "THIS_ALC: COMPLETE ")
					

if __name__=='__main__':

	""" 
	
	Allows commandline calls to main().
	
	      	
	"""	
	
	main(sys.argv[1:])
