# vim: ts=3:sw=3
"""
This module allows to import model definitions from FeynRules using the
Python interface.
"""

import os
import os.path
import imp
import golem.model.expressions as ex

from golem.util.tools import error, warning, message, debug, \
		LimitedWidthOutputStream

LINE_STYLES = {
		'straight': 'fermion',
		'wavy': 'photon',
		'curly': 'gluon',
		'dashed': 'scalar',
		'dotted': 'ghost'
}

sym_cmath = ex.SymbolExpression("cmath")
sym_exp   = ex.SymbolExpression("exp")
sym_log   = ex.SymbolExpression("log")
sym_sqrt  = ex.SymbolExpression("sqrt")
sym_sin   = ex.SymbolExpression("sin")
sym_cos   = ex.SymbolExpression("cos")
sym_tan   = ex.SymbolExpression("tan")
sym_asin  = ex.SymbolExpression("asin")
sym_acos  = ex.SymbolExpression("acos")
sym_atan  = ex.SymbolExpression("atan")
sym_sinh  = ex.SymbolExpression("sinh")
sym_cosh  = ex.SymbolExpression("cosh")
sym_tanh  = ex.SymbolExpression("tanh")
sym_asinh = ex.SymbolExpression("asinh")
sym_acosh = ex.SymbolExpression("acosh")
sym_atanh = ex.SymbolExpression("atanh")
sym_pi    = ex.SymbolExpression("pi")
sym_e     = ex.SymbolExpression("e")

sym_re    = ex.SpecialExpression("re")
sym_im    = ex.SpecialExpression("im")
sym_sec   = ex.SpecialExpression("sec")
sym_csc   = ex.SpecialExpression("csc")
sym_asec  = ex.SpecialExpression("asec")
sym_acsc  = ex.SpecialExpression("acsc")
sym_conjg = ex.SpecialExpression("complexconjugate")
sym_cmplx = ex.SpecialExpression("complex")

sym_Nf    = ex.SpecialExpression("Nf")
sym_Nfgen = ex.SpecialExpression("Nfgen")
sym_Nfrat = ex.SpecialExpression("Nfrat")
sym_NC    = ex.SpecialExpression("NC")
sym_if    = ex.SpecialExpression("if")

i_ = ex.SpecialExpression("i_")

cmath_functions = [
		sym_exp, sym_log, sym_sqrt, sym_sin, sym_cos, sym_tan,
		sym_asin, sym_acos, sym_atan, sym_sinh, sym_cosh, sym_tanh,
		sym_asinh, sym_acosh, sym_atanh, sym_pi, sym_e
	]

shortcut_functions = [
		sym_re, sym_im, sym_sec, sym_csc, sym_asec, sym_acsc,
		sym_conjg, sym_cmplx, sym_if
	]

unprefixed_symbols = [
		sym_Nf, sym_Nfgen, sym_Nfrat
	]

class Model:
	def __init__(self, model_path):
		mfile = None
		try:
			parent_path = os.path.normpath(os.path.join(model_path, os.pardir))
			norm_path = os.path.normpath(model_path)
			assert norm_path.startswith(parent_path), "Don't know what to do!"
			mname = norm_path[len(parent_path):].replace(os.sep, "")
			if os.altsep is not None:
				mname = mname.replace(os.altsep, "")
			search_path = [ parent_path ]

			message("Trying to import FeynRules model '%s' from %s" %
					(mname, search_path[0]))
			mfile, mpath, mdesc = imp.find_module(mname, search_path)
			mod = imp.load_module(mname, mfile, mpath, mdesc)
		except ImportError as exc:
			error("Problem importing model file: %s" % exc)
		finally:
			if mfile is not None:
				mfile.close()

		self.all_particles  = mod.all_particles
		self.all_couplings  = mod.all_couplings
		self.all_parameters = mod.all_parameters
		self.all_vertices   = mod.all_vertices
		self.all_lorentz    = mod.all_lorentz
		self.model_orig = model_path
		self.model_name = mname
		self.prefix = "mdl"
		self.floats = []

		parser = ex.ExpressionParser()
		for l in self.all_lorentz:
			name = l.name
			structure = parser.compile(l.structure)
			l.rank = get_rank(structure)

	def write_python_file(self, f):
		f.write("# vim: ts=3:sw=3\n")
		f.write("# This file has been generated from the FeynRules model files\n")
		f.write("# in %s\n" % self.model_orig)
		f.write("from golem.model.particle import Particle\n")
		f.write("\nmodel_name = %r\n\n" % self.model_name)

		message("      Generating particle list ...")
		f.write("particles = {")

		is_first = True

		mnemonics = {}
		latex_names = {}
		line_types = {}

		for p in self.all_particles:
			if is_first:
				is_first = False
				f.write("\n")
			else:
				f.write(",\n")

			pmass = str(p.mass)
			pwidth = str(p.width)

			pdg_code = p.pdg_code
			canonical_name, canonical_anti = canonical_field_names(p)

			mnemonics[p.name] = canonical_name
			latex_names[canonical_name] = p.texname

			line_type = p.line.lower()
			if line_type in LINE_STYLES:
				line_types[canonical_name] = LINE_STYLES[line_type]
			else:
				line_types[canonical_name] = 'scalar'

			if pmass == "0" or pmass == "ZERO":
				mass = 0
			else:
				mass = self.prefix + pmass

			spin = abs(p.spin) - 1
			if canonical_name.startswith("anti"):
				spin = - spin

			if pwidth == "0" or pwidth == "ZERO":
				width = "0"
			else:
				width = self.prefix + pwidth

			f.write("\t%r: Particle(%r, %d, %r, %d, %r, %r, %d)" %
					(canonical_name, canonical_name, spin, mass,
						p.color, canonical_anti, width, pdg_code))

		f.write("\n}\n\n")

		is_first = True
		f.write("mnemonics = {")
		for key, value in mnemonics.items():
			if is_first:
				is_first = False
				f.write("\n")
			else:
				f.write(",\n")

			f.write("\t%r: particles[%r]" % (key, value))
		f.write("\n}\n\n")

		is_first = True
		f.write("latex_names = {")
		for key, value in latex_names.items():
			if is_first:
				is_first = False
				f.write("\n")
			else:
				f.write(",\n")

			f.write("\t%r: %r" % (key, value))
		f.write("\n}\n\n")

		is_first = True
		f.write("line_styles = {")
		for key, value in line_types.items():
			if is_first:
				is_first = False
				f.write("\n")
			else:
				f.write(",\n")

			f.write("\t%r: %r" % (key, value))
		f.write("\n}\n\n")


		parameters = {}
		functions = {}
		types = {}
		slha_locations = {}
		for p in self.all_parameters:
			name = self.prefix + p.name
			if p.nature == 'external':
				parameters[name] = p.value
				slha_locations[name] = (p.lhablock, p.lhacode)
			elif p.nature == 'internal':
				functions[name] = p.value
			else:
				error("Parameter's nature ('%s') not implemented." % p.nature)

			if p.type == "real":
				types[name] = "R"
			elif p.type == "complex":
				types[name] = "C"
			else:
				error("Parameter's type ('%s') not implemented." % p.type)

		parameters['NC'] = '3.0'
		types['NC'] = 'R'
		parameters['Nf'] = '5.0'
		types['Nf'] = 'R'
		parameters['Nfgen'] = '-1.0'
		types['Nfgen'] = 'R'

		functions['Nfrat'] = 'if(Nfgen,Nf/Nfgen,1)'
		types['Nfrat'] = 'R'

		specials = {}
		for expr in shortcut_functions:
			specials[str(expr)] = expr
		for expr in unprefixed_symbols:
			specials[str(expr)] = expr

		parser = ex.ExpressionParser(**specials)

		for c in self.all_couplings:
			name = self.prefix + c.name.replace("_", "")
			functions[name] = c.value
			types[name] = "C"

		message("      Generating function list ...")
		f.write("functions = {")
		fcounter = [0]
		fsubs = {}
		is_first = True
		for name, value in functions.items():

			expr = parser.compile(value)
			for fn in cmath_functions:
				expr = expr.algsubs(ex.DotExpression(sym_cmath, fn),
						ex.SpecialExpression(str(fn)))
			expr = expr.prefixSymbolsWith(self.prefix)
			expr = expr.replaceFloats(self.prefix + "float", fsubs, fcounter)
			expr = expr.algsubs(sym_cmplx(
				ex.IntegerExpression(0), ex.IntegerExpression(1)), i_)

			if is_first:
				is_first = False
				f.write("\n")
			else:
				f.write(",\n")
			f.write("\t%r: " % name)
			f.write("'")
			expr.write(f)
			f.write("'")
		f.write("\n}\n\n")

		self.floats = list(fsubs.keys())

		f.write("parameters = {")
		is_first = True

		for name, value in fsubs.items():
			if is_first:
				is_first = False
				f.write("\n")
			else:
				f.write(",\n")
			f.write("\t%r: %r" % (name, str(value)))

		for name, value in parameters.items():
			if is_first:
				is_first = False
				f.write("\n")
			else:
				f.write(",\n")
			if isinstance(value, complex):
				f.write("\t%r: [%r, %r" % (name, str(value.real), str(value.imag)))
			else:
				f.write("\t%r: %r" % (name, str(value)))
		f.write("\n}\n\n")

		f.write("latex_parameters = {")
		is_first = True
		for p in self.all_parameters:
			name = self.prefix + p.name
			if is_first:
				is_first = False
			else:
				f.write(",") 
			f.write("\n\t%r: %r" % (name, p.texname)) 
		f.write("\n}\n\n")

		f.write("types = {")
		is_first = True

		for name in fsubs.keys():
			if is_first:
				is_first = False
				f.write("\n")
			else:
				f.write(",\n")
			f.write("\t%r: 'RP'" % name)

		for name, value in types.items():
			if is_first:
				is_first = False
				f.write("\n")
			else:
				f.write(",\n")
			f.write("\t%r: %r" % (name, value))
		f.write("\n}\n\n")

		f.write("slha_locations = {")
		is_first = True

		for name, value in slha_locations.items():
			if is_first:
				is_first = False
				f.write("\n")
			else:
				f.write(",\n")
			f.write("\t%r: %r" % (name, value))
		f.write("\n}\n\n")

	def write_qgraf_file(self, f):
		trunc_model = [self.model_orig]
		while len(trunc_model[-1]) > 70:
			s = trunc_model[-1]
			trunc_model[-1] = s[:69]
			trunc_model.append(s[69:])

		f.write("% vim: syntax=none\n\n")
		f.write("% This file has been generated from the FeynRule model files\n")
		f.write("%% in %s\n" % ("\\\n% ".join(trunc_model)))
		f.write("[ model = '%s' ]\n\n" % self.model_name)
		f.write("[ fmrules = '%s' ]\n\n" % self.model_name)

		f.write("%---#[ Propagators:\n")
		for p in self.all_particles:
			if p.pdg_code < 0:
				continue

			f.write("%% %s -- %s Propagator (PDG: %d)\n"
					% (p.name, p.antiname, p.pdg_code))

			field, afield = canonical_field_names(p)

			pmass = str(p.mass)
			pwidth = str(p.width)

			if pmass == "0" or pmass == "ZERO":
				mass = 0
			else:
				mass = self.prefix + pmass

			if p.spin % 2 == 1:
				if p.GhostNumber is not None:
					if p.GhostNumber == 1:
						sign = "-"
					else:
						sign = "+"
				else:
					sign = "+"

				if mass == 0:
					options = ", notadpole"
				else:
					options = ""
			else:
				sign = "-"
				options = ""

			if pwidth == "0" or pwidth == "ZERO":
				width = "0"
			else:
				width = self.prefix + pwidth

			if not p.propagating:
				aux = "+1"
			else:
				aux = "+0"

			if p.selfconjugate:
				conj = "('+')"
			else:
				conj = "('+','-')"

			f.write("[%s,%s,%s%s;TWOSPIN='%d',COLOR='%d',\n"
				% (field, afield, sign, options, abs(p.spin)-1, abs(p.color)))
			f.write("    MASS='%s', WIDTH='%s',\n"
				% (mass, width))
			f.write("    AUX='%s', CONJ=%s]\n"
				% (aux, conj))
					
		f.write("%---#] Propagators:\n")
		f.write("%---#[ Vertices:\n")

		lwf = LimitedWidthOutputStream(f, 70)

		orders = set()
		for c in self.all_couplings:
			orders.update(c.order.keys())

		for v in self.all_vertices:
			particles = v.particles
			names = []
			fields = []
			afields = []
			spins = []
			for p in particles:
				names.append(p.name)
				cn = canonical_field_names(p)
				fields.append(cn[0])
				afields.append(cn[1])
				spins.append(p.spin - 1)

			flip = spins[0] == 1 and spins[2] == 1

			vrank = 0
			for coord, coupling in v.couplings.items():
				ic, il = coord
				lrank = v.lorentz[il].rank
				if lrank > vrank:
					vrank = lrank

			vfunctions = {}
			vfunctions["RK"] = vrank
			for c in v.couplings.values():
				for name in orders:
					if name in c.order:
						power = c.order[name]
					else:
						power = 0

					if name in vfunctions:
						if vfunctions[name] != power:
							warning(("Vertex %s has ambiguous powers in %s (%d,%d). "
								% (v.name, vfunctions[name], power))
									+ "I will use %d." % vfunctions[name])
					else:
						vfunctions[name] = power

			f.write("%% %s: %s Vertex" % ( v.name, " -- ".join(names)))
			lwf.nl()
			lwf.write("[")
			is_first = True

			xfields = afields[:]
			if flip:
				xfields[0] = afields[1]
				xfields[1] = afields[0]

			for field in xfields:
				if is_first:
					is_first = False
				else:
					lwf.write(",")
				lwf.write(field)
			lwf.write(";")
			is_first = True
			for name, power in vfunctions.items():
				if is_first:
					is_first = False
				else:
					lwf.write(",")
				lwf.write("%s='%-d'" % (name, power))
			lwf.write("]")
			lwf.nl()

		f.write("%---#] Vertices:\n\n")

	def write_form_file(self, f):
		parser = ex.ExpressionParser()
		lorex = {}
		lsubs = {}
		lcounter = [0]
		dummy_found = {}
		for l in self.all_lorentz:
			name = l.name
			structure = parser.compile(l.structure)
			structure = structure.replaceStrings(
					"ModelDummyIndex", lsubs, lcounter)
			structure = structure.replaceNegativeIndices(0, "MDLIndex%d",
					dummy_found)
			for i in [2]:
				structure = structure.algsubs(
					ex.FloatExpression("%d." % i),
					ex.IntegerExpression("%d" % i))

			lorex[name] = transform_lorentz(structure, l.spins)

		lwf = LimitedWidthOutputStream(f, 70, 6)
		f.write("* vim: syntax=form:ts=3:sw=3\n\n")
		f.write("* This file has been generated from the FeynRule model files\n")
		f.write("* in %s\n\n" % self.model_orig)

		f.write("*---#[ Symbol Definitions:\n")
		f.write("*---#[ Fields:\n")

		fields = []
		for p in self.all_particles:
			part, anti = canonical_field_names(p)
			field = "[field.%s]" % part
			if field not in fields:
				fields.append(field)
			if part != anti:
				field = "[field.%s]" % anti
				if field not in fields:
					fields.append(field)

		if len(fields) > 0:
			if len(fields) == 1:
				f.write("Symbol %s;" % fields[0])
			else:
				f.write("Symbols")
				lwf.nl()
				lwf.write(fields[0])
				for p in fields[1:]:
					lwf.write(",")
					lwf.write(p)
				lwf.write(";")
		f.write("\n")
		f.write("*---#] Fields:\n")
		f.write("*---#[ Parameters:\n")

		params = []
		for p in self.all_parameters:
			params.append(self.prefix + p.name)

		for c in self.all_couplings:
			params.append(self.prefix + c.name.replace("_", ""))

		if len(params) > 0:
			if len(params) == 1:
				f.write("Symbol %s;" % params[0])
			else:
				f.write("Symbols")
				lwf.nl()
				lwf.write(params[0])
				for p in params[1:]:
					lwf.write(",")
					lwf.write(p)
				lwf.write(";")

		f.write("\n")

		if len(self.floats) == 1:
			f.write("Symbol %s;\n" % self.floats[0])
		elif len(self.floats) > 1:
			f.write("Symbols")
			lwf.nl()
			lwf.write(self.floats[0])
			for p in self.floats[1:]:
				lwf.write(",")
				lwf.write(p)
			lwf.write(";\n")

		f.write("AutoDeclare Indices ModelDummyIndex, MDLIndex;\n")
		f.write("*---#] Parameters:\n")
		f.write("*---#] Symbol Definitions:\n")
		if self.containsMajoranaFermions():
			f.write("* Model contains Majorana Fermions:\n")
			debug("You are working with a model " +
					"that contains Majorana fermions.")
			f.write("#Define DISCARDQGRAFSIGN \"1\"\n")
		f.write("#Define USEVERTEXPROC \"1\"\n")
		f.write("*---#[ Procedure ReplaceVertices :\n")
		f.write("#Procedure ReplaceVertices\n")

		for v in self.all_vertices:
			particles = v.particles
			names = []
			fields = []
			afields = []
			spins = []
			for p in particles:
				names.append(p.name)
				cn = canonical_field_names(p)
				fields.append(cn[0])
				afields.append(cn[1])
				spins.append(p.spin - 1)

			flip = spins[0] == 1 and spins[2] == 1
			deg = len(particles)

			xidx = range(deg)
			if flip:
				xidx[0] = 1
				xidx[1] = 0

			fold_name = "(%s) %s Vertex" % ( v.name, " -- ".join(names))
			f.write("*---#[ %s:\n" % fold_name)
			f.write("Identify Once vertex(iv?")
			colors = []
			for i in xidx:
				p = particles[i]
				field = afields[i]
				anti = fields[i]
				color = abs(p.color)
				spin = abs(p.spin) - 1
				if field.startswith("anti"):
					spin = - spin
					color = - color
				colors.append(color)

				f.write(",\n   [field.%s], idx%d?,%d,k%d?,idx%dL%d?,%d,idx%dC%d?"
						% (field, i+1, spin, i+1, i+1, abs(spin), color, i+1,
							abs(color)))
			f.write(") =")

			dummies = []
			for coord, coupling in v.couplings.items():
				ic, il = coord
				lorentz = lorex[v.lorentz[il].name]
				scolor = v.color[ic]
				f.write("\n   + %s"
						% (self.prefix + coupling.name.replace("_", "")))
				if scolor != "1":
					color = parser.compile(scolor)
					color = color.replaceStrings("ModelDummyIndex", lsubs, lcounter)
					color = color.replaceNegativeIndices(0, "MDLIndex%d",
							dummy_found)
					color = transform_color(color, colors, xidx)
					if lorentz == ex.IntegerExpression(1):
						expr = color
					else:
						expr = color * lorentz
				else:
					expr = lorentz
				if not expr == ex.IntegerExpression(1):
					f.write(" * (")
					lwf.nl()
					expr.write(lwf)
					f.write("\n   )")
			
				for ind in lsubs.values():
					s = str(ind)
					if expr.dependsOn(s):
						if s not in dummies:
							dummies.append(s)

			f.write(";\n")

			for idx in dummy_found.values():
				dummies.append(str(idx))

			if len(dummies) > 0:
				f.write("Sum %s;\n" % ", ".join(dummies))
			f.write("*---#] %s:\n" % fold_name)
		f.write("#EndProcedure\n")
		f.write("*---#] Procedure ReplaceVertices :\n")
		f.write("*---#[ Dummy Indices:\n")
		for ind in lsubs.values():
			f.write("Index %s;\n" % ind)
		f.write("*---#] Dummy Indices:\n")
		f.write("""\
*---#[ Procedure VertexConstants :
#Procedure VertexConstants
* Just a dummy, all vertex constants are already
* replaced in ReplaceVertices.
*
* This procedure might disappear in any future version of Golem
* so don't rely on it.
*
#EndProcedure
*---#] Procedure VertexConstants :
""")

	def containsMajoranaFermions(self):
		for p in self.all_particles:
			if p.spin % 2 == 0 and p.selfconjugate:
				return True
		return False

	def store(self, path, local_name):
		message("  Writing Python file ...")
		f = open(os.path.join(path, "%s.py" % local_name), 'w')
		self.write_python_file(f)
		f.close()

		message("  Writing QGraf file ...")
		f = open(os.path.join(path, local_name), 'w')
		self.write_qgraf_file(f)
		f.close()

		message("  Writing Form file ...")
		f = open(os.path.join(path, "%s.hh" % local_name), 'w')
		self.write_form_file(f)
		f.close()

def canonical_field_names(p):
	pdg_code = p.pdg_code
	if pdg_code < 0:
		canonical_name = "anti%d" % abs(pdg_code)
		if p.selfconjugate:
			canonical_anti = canonical_name
		else:
			canonical_anti = "part%d" % abs(pdg_code)
	else:
		canonical_name = "part%d" % pdg_code
		if p.selfconjugate:
			canonical_anti = canonical_name
		else:
			canonical_anti = "anti%d" % pdg_code

	return (canonical_name, canonical_anti)

lor_P = ex.SymbolExpression("P")
lor_Metric = ex.SymbolExpression("Metric")
lor_Identity = ex.SymbolExpression("Identity")
lor_Gamma = ex.SymbolExpression("Gamma")
lor_ProjP = ex.SymbolExpression("ProjP")
lor_ProjM = ex.SymbolExpression("ProjM")

lor_ProjMinus = ex.SymbolExpression("ProjMinus")
lor_ProjPlus = ex.SymbolExpression("ProjPlus")
lor_Sm = ex.SymbolExpression("Sm")
lor_d = ex.SymbolExpression("d")
lor_d1 = ex.SymbolExpression("d_")
lor_NCContainer = ex.SymbolExpression("NCContainer")
lor_Gamma5 = ex.SymbolExpression("Gamma5")

def get_rank(expr):
	if isinstance(expr, ex.SumExpression):
		n = len(expr)
		lst = [get_rank(expr[i]) for i in range(n)]
		if len(lst) == 0:
			return 0
		else:
			return max(lst)

	elif isinstance(expr, ex.ProductExpression):
		n = len(expr)
		result = 0

		for i in range(n):
			sign, factor = expr[i]
			result += get_rank(factor)
		return result

	elif isinstance(expr, ex.UnaryMinusExpression):
		return get_rank(expr.getTerm())

	elif isinstance(expr, ex.FunctionExpression):
		head = expr.getHead()
		args = expr.getArguments()
		if head == lor_P:
			return 1
		else:
			return 0
	else:
		return 0

def transform_lorentz(expr, spins):
	if isinstance(expr, ex.SumExpression):
		n = len(expr)
		return ex.SumExpression([transform_lorentz(expr[i], spins) 
			for i in range(n)])
	elif isinstance(expr, ex.ProductExpression):
		n = len(expr)
		new_factors = []

		for i in range(n):
			sign, factor = expr[i]
			new_factors.append( (sign, transform_lorentz(factor, spins)) )
		return ex.ProductExpression(new_factors)

	elif isinstance(expr, ex.UnaryMinusExpression):
		return ex.UnaryMinusExpression(
				transform_lorentz(expr.getTerm(), spins)
			)
	elif isinstance(expr, ex.FunctionExpression):
		head = expr.getHead()
		args = expr.getArguments()
		if head == lor_P:
			# P(index, momentum)
			if isinstance(args[0], ex.IntegerExpression):
				i = int(args[0])
				s = spins[i-1] - 1
				index = ex.SymbolExpression("idx%dL%d" % (i, s))
			else:
				index = args[0]

			mom = ex.SymbolExpression("k%d" % int(args[1]))
			# UFO files have all momenta outgoing:
			return -mom(index)
		elif head == lor_Metric or head == lor_Identity:
			my_spins = []
			if isinstance(args[0], ex.IntegerExpression):
				i = int(args[0])
				s = spins[i-1] - 1
				index1 = ex.SymbolExpression("idx%dL%d" % (i, s))
				my_spins.append(s)
			else:
				index1 = args[0]
			if isinstance(args[1], ex.IntegerExpression):
				i = int(args[1])
				s = spins[i-1] - 1
				index2 = ex.SymbolExpression("idx%dL%d" % (i, s))
				my_spins.append(s)
			else:
				index2 = args[1]

			if my_spins == [1, 1]:
				#return lor_d1(index1, index2)
				return lor_NCContainer(ex.IntegerExpression(1), index1, index2)
			else:
				return lor_d(index1, index2)
		elif head == lor_Gamma:
			if isinstance(args[1], ex.IntegerExpression):
				i = int(args[1])
				s = spins[i-1] - 1
				index2 = ex.SymbolExpression("idx%dL%d" % (i, s))
			else:
				index2 = args[1]
			if isinstance(args[2], ex.IntegerExpression):
				i = int(args[2])
				s = spins[i-1] - 1
				index3 = ex.SymbolExpression("idx%dL%d" % (i, s))
			else:
				index3 = args[2]
			if isinstance(args[0], ex.IntegerExpression):
				i = int(args[0])
				if i == 5:
					return lor_NCContainer(lor_Gamma5, index2, index3)
				else:
					s = spins[i-1] - 1
					index1 = ex.SymbolExpression("idx%dL%d" % (i, s))
			else:
				index1 = args[0]
			return lor_NCContainer(lor_Sm(index1), index2, index3)
		elif head == lor_ProjM:
			if isinstance(args[0], ex.IntegerExpression):
				i = int(args[0])
				s = spins[i-1] - 1
				index1 = ex.SymbolExpression("idx%dL%d" % (i, s))
			else:
				index1 = args[0]
			if isinstance(args[1], ex.IntegerExpression):
				i = int(args[1])
				s = spins[i-1] - 1
				index2 = ex.SymbolExpression("idx%dL%d" % (i, s))
			else:
				index2 = args[1]
			return lor_NCContainer(lor_ProjMinus, index1, index2)
		elif head == lor_ProjP:
			if isinstance(args[0], ex.IntegerExpression):
				i = int(args[0])
				s = spins[i-1] - 1
				index1 = ex.SymbolExpression("idx%dL%d" % (i, s))
			else:
				index1 = args[0]
			if isinstance(args[1], ex.IntegerExpression):
				i = int(args[1])
				s = spins[i-1] - 1
				index2 = ex.SymbolExpression("idx%dL%d" % (i, s))
			else:
				index2 = args[1]
			return lor_NCContainer(lor_ProjPlus, index1, index2)
		else:
			return expr
	else:
		return expr

col_T = ex.SymbolExpression("T")
col_f = ex.SymbolExpression("f")
col_Identity = ex.SymbolExpression("Identity")
col_d_ = ex.SymbolExpression("d_")

def transform_color(expr, colors, xidx):
	if isinstance(expr, ex.SumExpression):
		n = len(expr)
		return ex.SumExpression([transform_color(expr[i], colors, xidx)
			for i in range(n)])
	elif isinstance(expr, ex.ProductExpression):
		n = len(expr)
		new_factors = []

		for i in range(n):
			sign, factor = expr[i]
			new_factors.append( (sign, transform_color(factor, colors, xidx)) )
		return ex.ProductExpression(new_factors)

	elif isinstance(expr, ex.UnaryMinusExpression):
		return ex.UnaryMinusExpression(
				transform_color(expr.getTerm(), colors, xidx)
			)
	elif isinstance(expr, ex.FunctionExpression):
		head = expr.getHead()
		args = expr.getArguments()
		if head == col_T or head == col_f:
			indices = []
			order = []
			xi = []
			for j in range(3):
				if isinstance(args[j], ex.IntegerExpression):
					i = int(args[j])
					x = xidx[i-1]
					c = abs(colors[x])
					order.append(colors[x])
					xi.append(x)
					indices.append(ex.SymbolExpression("idx%dC%d" % (x+1, c)))
				else:
					indices.append(args[j])
					order.append(0)
					xi.append(-1)
			if head == col_T:
				if order == [8, -3, 0]:
					order[2] = 3
				elif order == [8, 0, 3]:
					order[1] = -3

				if order == [8, -3, 3]:
					return head(indices[0], indices[1], indices[2])
				elif order == [8, 3, -3]:
					return head(indices[0], indices[2], indices[1])
				else:
					error("Cannot recognize color assignment at vertex: %s" % order)
			else:
				return head(indices[0], indices[1], indices[2])
		if head == col_Identity:
			if isinstance(args[0], ex.IntegerExpression):
				i = int(args[0])
				c = abs(colors[i-1])
				index1 = ex.SymbolExpression("idx%dC%d" % (i, c))
			else:
				index1 = args[0]
			if isinstance(args[1], ex.IntegerExpression):
				i = int(args[1])
				c = abs(colors[i-1])
				index2 = ex.SymbolExpression("idx%dC%d" % (i, c))
			else:
				index2 = args[1]
			return col_d_(index1, index2)
		else:
			return expr
	else:
		return expr
