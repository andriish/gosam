# vim: ts=3:sw=3

"""
This file contains routines for the communication with QGraf
and is only used in golem-main.py
"""
import subprocess
import os.path
import os

import golem.properties
import golem.pyxo.pyxodraw
import golem.model.calchep

from golem.util.tools import copy_file, \
		debug, message, warning
from golem.util.path import golem_path
from golem.util.config import GolemConfigError
import golem.util.tools
import golem.util.constants as consts

def diagram_count(conf, loops, cut=0):
	"""
	Analyzes the file diagrams.<loops>.hh to
	infer the total number of diagrams in a
	process at the given loop order

	loops=0: leading order
	loops=1: NLO
	loops=2: counter-term graphs
	"""
	path = golem.util.tools.process_path(conf)

	ext  = ".hh"

	if loops == 0:
		present = conf.getBooleanProperty("generate_lo_diagrams")
		if present:
			fnames = [os.path.join(path, consts.PATTERN_DIAGRAMS_LO + ext)]
		else:
			return 0
	elif loops == 1:
		present = conf.getBooleanProperty("generate_nlo_virt")
		if present:
			fnames = [os.path.join(path, consts.PATTERN_DIAGRAMS_NLO_VIRT + ext)]
		else:
			return 0
	elif loops == 2:
		present = conf.getBooleanProperty("generate_uv_counterterms")
		if present:
			fnames = [os.path.join(path, consts.PATTERN_DIAGRAMS_CT + ext)]
		else:
			return 0
	else:
		raise NotImplementedError(
				"A value of loops=%d in diagram_count is not implemented."
				% loops)

	result = 0
	for fname in fnames:
		f = open(fname, 'r')
		for line in f:
			if line.strip().startswith("#define DIAGRAMCOUNT"):
				words = line.strip().split()
				result += int(words[2].strip('"'))
				break
		f.close()
	return result

def write_qgraf_dat(path, style, model, output_short_name, options, verbatim, \
		in_particles, out_particles, r_particles, loops):
	"""
	Prepares the file 'qgraf.dat' for the next subprocess.

	PARAMETER

	path -- the path where the file 'qgraf.dat' and the output file should go
	style -- name of the style file, must reside in 'path'
	model -- name of the model file, must reside in 'path'
	output_short_name -- the name of the output file generated by qgraf without the directory name
	options -- list of options for the line 'options=...;'
	verbatim -- list of propagator selections etc.
	in_particles -- list of incoming particles
	out_particles -- list of outgoing particles
	r_particles -- list, which is either empty or [RENO]
	loops -- number of loops, either 0 or 1

	SIDE EFFECTS

	Writes to the file qgraf.dat in the directory specified by 'path'. Creates it
	if necessary.
	"""
	assert (len(r_particles) == 0) or (len(r_particles) == 1 and loops == 1)

	qgraf_dat_name = os.path.join(path, "qgraf.dat")
	output_name = os.path.join(path, output_short_name)

	f = open(qgraf_dat_name, 'w')
	# write line: output = <file> ;
	f.write("output = %r;\n" % output_short_name)

	# write line style = <syle file> ;
	f.write("style = %r;\n" % style)

	# write line: model = <model file> ;
	f.write("model = %r;\n" % model)

	# write line: in = ... ;
	ki = 0
	f.write("in = ")
	comma = False
	for p in in_particles:
		if comma:
			f.write(", ")
		else:
			comma = True
		ki += 1
		f.write("%s[k%d]" % (str(p), ki))
	f.write(";\n")

	# write line: out = ... ;
	f.write("out = ")
	comma = False
	for p in out_particles:
		if comma:
			f.write(", ")
		else:
			comma = True
		ki += 1
		f.write("%s[k%d]" % (str(p), ki))

	# add r-particle if present
#	if len(r_particles) == 1:
#		if comma:
#			f.write(", ")
#		else:
#			comma = True
#		f.write("%s[ZERO]" % str(r_particles[0]))

	f.write(";\n")

	f.write("loops=%d;\nloop_momentum=p;\n" % loops)

	# write line: options = <opt1>, <opt2>, ...;
	f.write("options=%s;\n" % ", ".join(options))
	# genUV
	if len(r_particles) == 1:
		f.write("true=iprop[%s,1,1];\n" % str(r_particles[0]))

	# append verbatim lines
	f.write(verbatim)
	f.write("\n%------- EOF ----------\n")
	f.close()

def run_qgraf_dat(conf, output_short_name, log_name):
	path = golem.util.tools.process_path(conf)

	qgraf_bin = conf.getProperty(golem.properties.qgraf_bin)
	qgraf_bin = os.path.expandvars(qgraf_bin)

	output_name = os.path.join(path, output_short_name)

	if os.path.exists(output_name):
		os.remove(output_name)

	message("QGraf is generating %s" % output_short_name)

	f = open(os.path.join(path, log_name), 'w')
	try:
		subprocess.call([qgraf_bin], cwd=path, stdout=f)
	except OSError as ex:
		raise GolemConfigError(
				("QGraf (%r) has failed while processing 'qgraf.dat' in %r.\n" +
					("Error message: %s\n" % ex) +
					"Detailed output has been written to %r.")
				% (qgraf_bin, path, log_name))
	finally:
		f.close()

	if not os.path.exists(output_name):
		raise GolemConfigError(
				("QGraf did not succeed producing file %r.\n" +
					"Detailed output has been written to %r.")
				% (output_name, log_name))

def format_qgraf_verbatim(conf, prop):
	result = []
	verbatim = conf.getProperty(prop)
	lines = verbatim.splitlines()
	for line in lines:
		lhs, sep, rhs = line.partition(";")
		while rhs != "":
			result.append(lhs+sep)
			lhs, sep, rhs = rhs.partition(";")
		result.append(lhs+sep)
	return "\n".join(result)

def run_qgraf(conf, in_particles, out_particles):
	path = golem.util.tools.process_path(conf)

	powers = conf.getProperty(golem.properties.qgraf_power)
	options = conf.getProperty(golem.properties.qgraf_options)
	verbatim =     format_qgraf_verbatim(conf,
			golem.properties.qgraf_verbatim)
	verbatim_lo =  format_qgraf_verbatim(conf,
			golem.properties.qgraf_verbatim_lo)
	verbatim_nlo = format_qgraf_verbatim(conf,
			golem.properties.qgraf_verbatim_nlo)
	templates = conf.getProperty(golem.properties.template_path)
	templates = os.path.expandvars(templates)

	flag_generate_nlo_virt = conf.getBooleanProperty("generate_nlo_virt")
	flag_generate_lo_diagrams = conf.getBooleanProperty("generate_lo_diagrams")
	flag_generate_uv_counterterms = \
			conf.getBooleanProperty("generate_uv_counterterms")
	flag_draw_diagrams = conf.getProperty(golem.properties.pyxodraw)
	flag_topolopy = True

	if not (flag_generate_nlo_virt or
			flag_generate_lo_diagrams or flag_generate_uv_counterterms):
		# Should never happen but is not considered an error either.
		# nothing to do
		return

	# These are our default file names:
	pyxo_sty    = "pyxo.sty"
	form_sty    = "form.sty"
	topo_sty    = "topolopy.sty"

	form_ext    = ".hh"
	python_ext  = ".py"
	pyo_ext     = ".pyo"
	pyc_ext     = ".pyc"
	log_ext     = ".log"

	cleanup_files = [ "qgraf.dat", form_sty, pyxo_sty, topo_sty]

	if templates is None or len(templates) == 0:
		templates = golem_path("templates")

	# ----------------- LO PART -------------------------------------------
	if flag_generate_lo_diagrams:
		output_name = consts.PATTERN_DIAGRAMS_LO + form_ext
		log_name    = consts.PATTERN_DIAGRAMS_LO + log_ext
		
		if powers is not None:
			new_verbatim = verbatim + "\n" + verbatim_lo + "\n" + \
					"true=vsum[%s,%s,%s];\n" % (powers[0], powers[1], powers[1])
		else:
			new_verbatim = verbatim + "\n" + verbatim_lo

		write_qgraf_dat(path, form_sty, consts.MODEL_LOCAL, output_name,
				options, new_verbatim, in_particles, out_particles, [], 0)
		run_qgraf_dat(conf, output_name, log_name)

		if flag_draw_diagrams:
			output_name = consts.PATTERN_PYXO_LO + python_ext
			log_name    = consts.PATTERN_PYXO_LO + log_ext
			write_qgraf_dat(path, pyxo_sty, consts.MODEL_LOCAL, output_name,
				options, new_verbatim, in_particles, out_particles, [], 0)
			run_qgraf_dat(conf, output_name, log_name)
			golem.pyxo.pyxodraw.pyxodraw(os.path.join(path, output_name),
					conf=conf)
			for ext in [python_ext, pyo_ext, pyc_ext]:
				cleanup_files.append(consts.PATTERN_PYXO_LO + ext)

		if flag_topolopy:
			output_name = consts.PATTERN_TOPOLOPY_LO + python_ext
			log_name    = consts.PATTERN_TOPOLOPY_LO + log_ext
			write_qgraf_dat(path, topo_sty, consts.MODEL_LOCAL, output_name,
				options, new_verbatim, in_particles, out_particles, [], 0)
			run_qgraf_dat(conf, output_name, log_name)

	# ----------------- VIRTUAL PART --------------------------------------
	if flag_generate_nlo_virt:
		output_name = consts.PATTERN_DIAGRAMS_NLO_VIRT + form_ext
		log_name    = consts.PATTERN_DIAGRAMS_NLO_VIRT + log_ext
		
		if powers is not None:
			new_verbatim = verbatim + "\n" + verbatim_nlo + "\n" + \
					"true=vsum[%s,%s,%s];\n" % (powers[0], powers[2], powers[2])
		else:
			new_verbatim = verbatim + "\n" + verbatim_nlo

		write_qgraf_dat(path, form_sty, consts.MODEL_LOCAL, output_name,
				options, new_verbatim, in_particles, out_particles, [], 1)
		run_qgraf_dat(conf, output_name, log_name)

		if flag_draw_diagrams:
			output_name = consts.PATTERN_PYXO_NLO_VIRT + python_ext
			log_name    = consts.PATTERN_PYXO_NLO_VIRT + log_ext
			write_qgraf_dat(path, pyxo_sty, consts.MODEL_LOCAL, output_name,
				options, new_verbatim, in_particles, out_particles, [], 1)
			run_qgraf_dat(conf, output_name, log_name)
			golem.pyxo.pyxodraw.pyxodraw(os.path.join(path, output_name),
					conf=conf)
			for ext in [python_ext, pyo_ext, pyc_ext]:
				cleanup_files.append(consts.PATTERN_PYXO_NLO_VIRT + ext)

		if flag_topolopy:
			output_name = consts.PATTERN_TOPOLOPY_VIRT + python_ext
			log_name    = consts.PATTERN_TOPOLOPY_VIRT + log_ext
			write_qgraf_dat(path, topo_sty, consts.MODEL_LOCAL, output_name,
				options, new_verbatim, in_particles, out_particles, [], 1)
			run_qgraf_dat(conf, output_name, log_name)

	# ----------------- UV COUNTERTERMS -----------------------------------
	# This doesn't work...at some point it would be better to add the RENO
	# fields automatically
	# Edited on 16.11.12
	if flag_generate_uv_counterterms:
		output_name = consts.PATTERN_DIAGRAMS_CT + form_ext
		log_name    = consts.PATTERN_DIAGRAMS_CT + log_ext
		
		if powers is not None:
			new_verbatim = verbatim + "\n" + \
					"true=vsum[%s,%s,%s];\n" % (powers[0], str(int(powers[2])-6), str(int(powers[2])-6))
		else:
			new_verbatim = verbatim

		write_qgraf_dat(path, form_sty, consts.MODEL_LOCAL, output_name, \
				options, new_verbatim, in_particles, out_particles, \
				["RENO"], 1)
		run_qgraf_dat(conf, output_name, log_name)

		if flag_draw_diagrams:
			output_name = consts.PATTERN_PYXO_CT + python_ext
			log_name    = consts.PATTERN_PYXO_CT + log_ext
			write_qgraf_dat(path, pyxo_sty, consts.MODEL_LOCAL, output_name,
				options, new_verbatim, in_particles, out_particles, \
				["RENO"], 1)
			run_qgraf_dat(conf, output_name, log_name)
			golem.pyxo.pyxodraw.pyxodraw(os.path.join(path, output_name),
					conf=conf)
			for ext in [python_ext, pyo_ext, pyc_ext]:
				cleanup_files.append(consts.PATTERN_PYXO_CT + ext)
		if flag_topolopy:
			output_name = consts.PATTERN_TOPOLOPY_CT + python_ext
			log_name    = consts.PATTERN_TOPOLOPY_CT + log_ext
			write_qgraf_dat(path, topo_sty, consts.MODEL_LOCAL, output_name,
				options, new_verbatim, in_particles, out_particles, [], 1)
			run_qgraf_dat(conf, output_name, log_name)

	# Clean up and leave
	qgraf_dat_name = os.path.join(path, "qgraf.dat")
	for filename in cleanup_files:
		full_name = os.path.join(path, filename)
		if os.path.exists(full_name):
			os.remove(full_name)

	if flag_generate_lo_diagrams and diagram_count(conf, 0) == 0 \
				and flag_generate_nlo_virt:
		warning("There are no tree-level diagrams for your setup.\n" +
				"!!! YOU WILL ALWAYS GET ZERO !!!\n" +
			  ("You probably wanted 'order=%s,NONE,%s'" % (powers[0], powers[2])) +
			  (" instead of 'order=%s'\n" % (",".join(map(str,powers)))) +
			  "in order to compute the |virtual|^2.")

