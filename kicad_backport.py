# kicad_backport - port back from .kicad_sym to .lib/.dcm
# and extract -cache.lib from .kicad_sch
#
# No warranties, use at your own risk
#
# Victor Joukov 2020-08-11

import sys
import os
import sexpdata


class Effects:
    def __init__(self, body=None):
        # effects.font.size
        self.font_size = 1.27, 1.27
        # effects.font[2:]
        self.font_italic = False
        self.font_bold = False
        self.font_var = ''
        # effects.hide
        self.hide = False
        # effects.justify
        self.justify_x = 'center'
        self.justify_y = 'center'
        if body: self.parse(body)

    def parse(self, body):
        for effect in body:
            if type(effect) == list:
                ef_name = effect[0].value()
                if ef_name == 'font':
                    for el in effect[1:]:
                        if type(el) == list:
                            if el[0].value() == 'size':
                                self.font_size = el[1:]
                        else:
                            val = el.value()
                            if val == 'italic':
                                self.font_italic = True
                            elif val == 'bold':
                                self.font_bold = True
                elif ef_name == 'justify':
                    self.justify_x = effect[1].value() # left, center, right
                    if len(effect) > 2:
                        self.justify_y = effect[2].value() # top, center, bottom
            else:
                if effect.value() == 'hide':
                    self.hide = True


class Property:
    def __init__(self, body):
        self.text = ''
        self.id = -1
        self.at = 0,0,0 # x, y, angle
        self.effects = Effects()
        if body: self.parse(body)
    def parse(self, body):
        self.text = body[0]
        for entry in body[1:]:
            e_type = entry[0].value()
            if e_type == 'id':
                self.id = entry[1]
            elif e_type == 'at':
                self.at = tuple(entry[1:])
            elif e_type == 'effects':
                self.effects = Effects(entry[1:])
    def serialize_lib(self, print_text=True):
        x = int(self.at[0]*1000/25.4)
        y = int(self.at[1]*1000/25.4)
        font_size = int(self.effects.font_size[0]*1000/25.4)
        direction = 'H' if self.at[2] == 0 else 'V'
        visibility = 'I' if self.effects.hide else 'V'
        j_x = self.effects.justify_x[0].upper()
        j_y = self.effects.justify_y[0].upper()
        slant = 'I' if self.effects.font_italic else 'N'
        weight = 'B' if self.effects.font_bold else 'N'
        text = self.text if print_text else ''
        return f'"{text}" {x} {y} {font_size} {direction} {visibility} {j_x} {j_y}{slant}{weight}'


# Symbol drawing primitives

class Text:
    def __init__(self, n_unit, n_subunit, body):
        self.n_unit = n_unit
        self.n_subunit = n_subunit
        self.text = body[0]
        self.at = 0,0,0
        self.effects = Effects()
        for entry in body[1:]:
            e_type = entry[0].value()
            if e_type == 'at':
                self.at = tuple(entry[1:])
            elif e_type == 'effects':
                self.effects = Effects(entry[1:])
    def serialize_lib(self):
        x = int(self.at[0]*1000/25.4)
        y = int(self.at[1]*1000/25.4)
        # NB! angle in classic lib and in kicad_sym for text is in 10ths of degree
        # as opposed to Arc where lib uses 10ths of degree and kicad_lib - float degrees
        angle = self.at[2]
        if self.text.find(' ') >= 0:
            text = '"' + self.text + '"'
        else:
            text = self.text
        font_size = int(self.effects.font_size[0]*1000/25.4)
        slant = 'Italic' if self.effects.font_italic else 'Normal'
        weight = 1 if self.effects.font_bold else 0
        j_x = self.effects.justify_x[0].upper()
        j_y = self.effects.justify_y[0].upper()
        return f'T {angle} {x} {y} {font_size} 0 {self.n_unit} {self.n_subunit} {text} {slant} {weight} {j_x} {j_y}'


# Superclass for pen-based primitives - Rectangle, Polyline, Arc, and Circle
class Pen:
    def __init__(self, n_unit, n_subunit, body):
        self.n_unit = n_unit
        self.n_subunit = n_subunit
        self.stroke_width = 0.254
        self.fill_type = 'none'

    def parse_entry(self, entry):
        e_type = entry[0].value()
        if e_type == 'stroke':
            # (stroke (width 0.254))
            self.stroke_width = entry[1][1]
        elif e_type == 'fill':
            # (fill (type background))
            self.fill_type = entry[1][1].value()
        else:
            return False
        return True

    def lib_get_stroke_width(self):
        return int(self.stroke_width*1000/25.4)
    def lib_get_fill_type(self):
        fill_type = 'N'
        if self.fill_type == 'background':
            fill_type = 'f'
        elif self.fill_type == 'outline':
            fill_type = 'F'
        return fill_type


class Rectangle(Pen):
    def __init__(self, n_unit, n_subunit, body):
        super().__init__(n_unit, n_subunit, body)
        self.start = 0,0
        self.end = 0,0
        for entry in body:
            e_type = entry[0].value()
            if e_type == 'start':
                self.start = tuple(entry[1:])
            elif e_type == 'end':
                self.end = tuple(entry[1:])
            else:
                self.parse_entry(entry)
    def serialize_lib(self):
        start_x = int(self.start[0]*1000/25.4)
        start_y = int(self.start[1]*1000/25.4)
        end_x = int(self.end[0]*1000/25.4)
        end_y = int(self.end[1]*1000/25.4)
        stroke_width = self.lib_get_stroke_width()
        fill_type = self.lib_get_fill_type()
        return f'S {start_x} {start_y} {end_x} {end_y} {self.n_unit} {self.n_subunit} {stroke_width} {fill_type}'


class Arc(Pen):
    def __init__(self, n_unit, n_subunit, body):
        super().__init__(n_unit, n_subunit, body)
        self.start = 0,0
        self.end = 0,0
        self.radius_at = 0,0
        self.radius_len = 0
        self.radius_angles = 0,0
        for entry in body:
            e_type = entry[0].value()
            if e_type == 'start':
                self.start = tuple(entry[1:])
            elif e_type == 'end':
                self.end = tuple(entry[1:])
            elif e_type == 'radius':
                for el in entry[1:]:
                    el_type = el[0].value()
                    if el_type == 'at':
                        self.radius_at = tuple(el[1:])
                    elif el_type == 'length':
                        self.radius_len = el[1]
                    elif el_type == 'angles':
                        self.radius_angles = tuple(el[1:])
            else:
                self.parse_entry(entry)
    def serialize_lib(self):
        r_x = int(self.radius_at[0]*1000/25.4)
        r_y = int(self.radius_at[1]*1000/25.4)
        r_l = int(self.radius_len*1000/25.4)
        a_0 = int(self.radius_angles[0]*10)
        a_1 = int(self.radius_angles[1]*10)
        start_x = int(self.start[0]*1000/25.4)
        start_y = int(self.start[1]*1000/25.4)
        end_x = int(self.end[0]*1000/25.4)
        end_y = int(self.end[1]*1000/25.4)
        stroke_width = self.lib_get_stroke_width()
        fill_type = self.lib_get_fill_type()
        return f'A {r_x} {r_y} {r_l} {a_0} {a_1} {self.n_unit} {self.n_subunit} {stroke_width} {fill_type} {start_x} {start_y} {end_x} {end_y}'


class Circle(Pen):
    def __init__(self, n_unit, n_subunit, body):
        super().__init__(n_unit, n_subunit, body)
        self.center = 0, 0
        self.radius = 0
        for entry in body:
            e_type = entry[0].value()
            if e_type == 'center':
                self.center = tuple(entry[1:])
            if e_type == 'radius':
                self.radius = entry[1]
            else:
                self.parse_entry(entry)
    def serialize_lib(self):
        x = int(self.center[0]*1000/25.4)
        y = int(self.center[1]*1000/25.4)
        r = int(self.radius*1000/25.4)
        stroke_width = self.lib_get_stroke_width()
        fill_type = self.lib_get_fill_type()
        return f'C {x} {y} {r} {self.n_unit} {self.n_subunit} {stroke_width} {fill_type}'


class Polyline(Pen):
    def __init__(self, n_unit, n_subunit, body):
        super().__init__(n_unit, n_subunit, body)
        self.pts = []
        for entry in body:
            e_type = entry[0].value()
            if e_type == 'pts':
                for el in entry[1:]:
                    if el[0].value() == 'xy':
                        self.pts.append(tuple(el[1:]))
            else:
                self.parse_entry(entry)
    def serialize_lib(self):
        n_pts = len(self.pts)
#        print(self.pts)
        points = ' '.join(map(lambda x: str(int(x*1000/25.4)), [item for sublist in self.pts for item in sublist]))
        stroke_width = self.lib_get_stroke_width()
        fill_type = self.lib_get_fill_type()
        return f'P {n_pts} {self.n_unit} {self.n_subunit} {stroke_width} {points} {fill_type}'


class Pin:
    pin_type_map = {
        'input' : 'I',
        'output': 'O',
        'passive' : 'P',
        'power_in' : 'W',
        'power_out' : 'w',
        'bidirectional' : 'B',
        'unspecified' : 'U',
        'tri_state' : 'T',
        'unconnected' : 'N',
        'open_emitter' :'E',
        'open_collector': 'C'
    }
    pin_style_map = {
        'line' : '',
        'clock' : 'C',
        'clock_low' : 'CL',
        'edge_clock_high' : 'F',
        'inverted' : 'I',
        'inverted_clock' : 'IC',
        'non_logic' : 'X',
        'input_low' : 'L',
        'output_low' : 'V'
    }
    def __init__(self, n_unit, n_subunit, body):
        self.n_unit = n_unit
        self.n_subunit = n_subunit
        self.at = 0,0,0
        self.length = 0
        self.name = ''
        self.name_effects = Effects()
        self.number = ''
        self.number_effects = Effects()
        self.hidden = False
        # input (I), output (O), passive (P), power_in (W), power_out(w),
        # bidirectional (B), unspecified (U), tri_state (T), unconnected (N)
        # open_emitter(E), open_collector(C)
        self.pin_type = body[0].value()
        self.pin_style = body[1].value()
        for entry in body[2:]:
            if type(entry) == list:
                e_type = entry[0].value()
                if e_type == 'at':
                    self.at = tuple(entry[1:])
                elif e_type == 'length':
                    self.length = entry[1]
                elif e_type == 'name':
                    self.name = entry[1]
                    for el in entry[2:]:
                        if type(el) == list and el[0].value() == 'effects':
                            self.name_effects = Effects(el[1:])
                elif e_type == 'number':
                    self.number = entry[1]
#                    print(f'pin number {self.number}')
                    for el in entry[2:]:
#                        print(el)
                        if type(el) == list and el[0].value() == 'effects':
                            self.number_effects = Effects(el[1:])
            else:
                e_type = entry.value()
                if e_type == 'hide':
                    self.hidden = True
    def serialize_lib(self):
        x = int(self.at[0]*1000/25.4)
        y = int(self.at[1]*1000/25.4)
        l = int(self.length*1000/25.4)
        angle = self.at[2]
        direction = ['R', 'U', 'L', 'D'][int((angle+45)/90)%4]
        fsize_name = int(self.name_effects.font_size[0]*1000/25.4)
        fsize_num = int(self.number_effects.font_size[0]*1000/25.4)
        pin_type = self.pin_type_map[self.pin_type]
        pin_style = self.pin_style_map[self.pin_style]
        if self.hidden:
            pin_style = 'N' + pin_style
        if pin_style:
            pin_style = ' ' + pin_style
        return f'X {self.name} {self.number} {x} {y} {l} {direction} {fsize_num} {fsize_name} {self.n_unit} {self.n_subunit} {pin_type}{pin_style}'
    

class Unit:
    element_map = {
        'rectangle' : Rectangle,
        'polyline' : Polyline,
        'arc' : Arc,
        'circle' : Circle,
        'text' : Text,
        'pin' : Pin
    }
    def __init__(self, n_unit, subunit, body):
        self.elements = []
        self.n_unit = n_unit
        self.n_subunit = subunit
        if body: self.parse(body)
    def parse(self, body):
        for el in body:
            el_type = el[0].value()
            self.elements.append(self.element_map[el_type](self.n_unit, self.n_subunit, el[1:]))
#        print(body[0])
    def __str__(self):
        return '\n'.join(self.elements)


class Symbol:
    def __init__(self, libname, name, body):
        self.libname = libname
        self.name = name
        self.extends = ''
        self.pin_numbers_hide = False
        self.pin_numbers_offset = 0
        self.pin_names_hide   = False
        self.pin_names_offset = 1.016 # 40mils default
        self.reference = None    # lib.F0
        self.value = None        # lib.F1
        self.footprint = None    # lib.F2
        self.datasheet = None    # text to dcm.F, everything else to lib.F3
        self.keywords = None     # dcm.K
        self.description = None  # dcm.D
        self.fplist = None       # $FPLIST
        self.locked = False
        self.power = False
        self.aliases = []        # ALIAS
        self.units = []          # DRAW
        if body: self.parse(body)
    def parse(self, body):
        for entry in body:
            e_type = entry[0].value()
            if e_type == 'property':
                e_name = entry[1]
                prop = Property(entry[2:])
#                print(f'prop {e_name}', prop)
                if e_name == 'Reference': self.reference = prop
                elif e_name == 'Value': self.value = prop
                elif e_name == 'Footprint': self.footprint = prop
                elif e_name == 'Datasheet': self.datasheet = prop
                elif e_name == 'ki_keywords': self.keywords = prop
                elif e_name == 'ki_description': self.description = prop
                elif e_name == 'ki_fp_filters': self.fplist = prop
                elif e_name == 'ki_locked': self.locked = True
                else:
                    print(f'Unknown property: {e_name}')
            elif e_type == 'symbol':
                # DRAW
                e_name = entry[1]
                parts = e_name.split('_')
                # Unit is for multiunit symbols.
                # Unit numbering starts from 1
                # Unit 0 - shared between all units
                n_unit = int(parts[-2])
                # Subunit actually represents DeMorgan body style
                # Same rules for numbering as for unit
                subunit = int(parts[-1])
#                print(f'  symbol {e_name}, {number}, {entry[2]}')
                self.units.append(Unit(n_unit, subunit, entry[2:]))
            elif e_type == 'extends':
                # ALIAS of reference to this symbol
                self.extends = entry[1]
            elif e_type == 'power':
                self.power = True
            elif e_type == 'pin_numbers':
                for effect in entry[1:]:
                    if type(effect) == list:
                        if effect[0].value() == 'offset':
                            self.pin_numbers_offset = effect[1]
                    elif effect.value() == 'hide':
                        self.pin_numbers_hide = True
            elif e_type == 'pin_names':
                for effect in entry[1:]:
                    if type(effect) == list:
                        if effect[0].value() == 'offset':
                            self.pin_names_offset = effect[1]
                    elif effect.value() == 'hide':
                        self.pin_names_hide = True
            else:
                print(f'Unknown symbol entry: {e_type}')

    def serialize_lib(self, cache_lib=False):
        pin_numbers_offset = int(self.pin_numbers_offset*1000/25.4)
        pin_numbers_show = 'N' if self.pin_numbers_hide else 'Y'
        pin_names_offset = int(self.pin_names_offset*1000/25.4)
        pin_names_show = 'N' if self.pin_names_hide else 'Y'
        name = self.libname + '_' + self.name if cache_lib else self.name
        locked = 'L' if self.locked else 'F'
        power = 'P' if self.power else 'N'
        n_units = 0
        units = set()
        texts = []
        circles = []
        arcs = []
        rectangles = []
        polylines = []
        pins = []
        for unit in self.units:
            for element in unit.elements:
                if type(element) == Text:
                    texts.append(element)
                elif type(element) == Arc:
                    arcs.append(element)
                elif type(element) == Circle:
                    circles.append(element)
                elif type(element) == Rectangle:
                    rectangles.append(element)
                elif type(element) == Polyline:
                    polylines.append(element)
                elif type(element) == Pin:
                    pins.append(element)
            if unit.n_unit > 0:
                units.add(unit.n_unit)
        # This is not very reliable, if last unit
        # doesn't have any elements specific to it
        # we can't find about its existence
        if units:
            n_units = max(units)
        else:
            n_units = 1
        lines = []
        lines.append('#')
        lines.append(f'# {name}')
        lines.append('#')
        lines.append(f'DEF {name} {self.reference.text} {pin_numbers_offset} {pin_names_offset} {pin_numbers_show} {pin_names_show} {n_units} {locked} {power}')
        lines.append(f'F0 {self.reference.serialize_lib()}') 
        lines.append(f'F1 {self.value.serialize_lib()}') 
        lines.append(f'F2 {self.footprint.serialize_lib()}') 
        lines.append(f'F3 {self.datasheet.serialize_lib(False)}') # text should be empty, goes to dcm.K
        if self.aliases: 
            lines.append(f'ALIAS {" ".join(self.aliases)}')
        if self.fplist:
            lines.append('$FPLIST')
            lines.append(f' {self.fplist.text}')
            lines.append('$ENDFPLIST')
        lines.append('DRAW')
        for el in arcs:
            lines.append(el.serialize_lib())
        for el in circles:
            lines.append(el.serialize_lib())
        for el in texts:
            lines.append(el.serialize_lib())
        for el in rectangles:
            lines.append(el.serialize_lib())
        for el in polylines:
            lines.append(el.serialize_lib())
        for el in pins:
            lines.append(el.serialize_lib())
        lines.append('ENDDRAW')
        lines.append('ENDDEF')
        return '\n'.join(lines)
    def serialize_dcm(self):
        has_description = self.description and self.description.text
        has_keywords = self.keywords and self.keywords.text
        has_datasheet = self.datasheet and self.datasheet.text
        if not (has_datasheet or has_description or has_keywords):
            return ''
        lines = []
        lines.append('#')
        lines.append(f'$CMP {self.name}')
        if has_description:
            lines.append(f'D {self.description.text}')
        if has_keywords:
            lines.append(f'K {self.keywords.text}')
        if has_datasheet:
            lines.append(f'F {self.datasheet.text}')
        lines.append('$ENDCMP')
        return '\n'.join(lines)


class Library:
    def __init__(self, body):
        self.symbols = {}
        symbols = {}
        ordinal = 0
        for entry in body:
            e_type = entry[0].value()
            if e_type == 'symbol':
                e_name = entry[1]
                libname = ''
                parts = e_name.split(':')
                if len(parts) > 1:
                    libname = parts[0]
                    name = parts[1]
                else:
                    name = e_name
                sym = Symbol(libname, name, entry[2:])
                symbols[name] = ordinal, sym
                ordinal += 1
        for _, sym in symbols.values():
#            print(sym)
            if sym.extends:
                symbols[sym.extends][1].aliases.append(sym.name)
        self.symbols = symbols
    def serialize_lib(self, cache_lib=False):
        syms_order = list(filter(lambda x: not x[1].extends, self.symbols.values()))
        syms_order.sort()
        header = '''\
EESchema-LIBRARY Version 2.4
#encoding utf-8
'''
        footer = '''
#
#End Library
'''
        return header + '\n'.join([sym.serialize_lib(cache_lib) for _, sym in syms_order]) + footer
    def serialize_dcm(self):
        syms_order = list(self.symbols.values())
        syms_order.sort()
        header = '''\
EESchema-DOCLIB  Version 2.0
'''
        footer = '''
#
#End Doc Library
'''
        entries = [sym.serialize_dcm() for _, sym in syms_order]
        return header + '\n'.join([x for x in entries if x]) + footer


# TODO: Parse and serialize schematics    
class Schematics:
    def __init__(self):
        pass
    def parse_entry(self, entry):
        e_type = entry[0].value()
        if e_type == 'junction':
            pass
        elif e_type == 'no_connect':
            pass
        elif e_type == 'wire':
            pass
        elif e_type == 'label':
            pass
        elif e_type == 'symbol':
            pass
        elif e_type == 'path':
            pass


def main():
    if len(sys.argv) < 2:
        print("Usage: kicad_backport.py FILE_NAME")
        return 1
    fn = sys.argv[1]
    with open(fn, "rt") as f:
        text = f.read()
    sexpr = sexpdata.loads(text)
    cache_lib = False
    if sexpr[0] == sexpdata.Symbol('kicad_symbol_lib'):
        # KiCad symbol library new format 
        # First element - symbol kicad_symbol_lib
        # Rest - lists with first symbol is key, rest represent value
        # version: 20200629
        # host: kicad_symbol_editor "version"
        # symbol PART_NAME
        body = sexpr[1:]
    elif sexpr[0] == sexpdata.Symbol('kicad_sch'):
        # KiCad schematics new format
        cache_lib = True
        sch = Schematics()
        for entry in sexpr[1:]:
            e_type = entry[0].value()
            if e_type == 'lib_symbols':
                body = entry[1:]
            else:
                sch.parse_entry(entry)
    else:
        print("Invalid symbol lib")
        return 2
    library = Library(body)
    fn_base, _ = os.path.splitext(fn)
    if cache_lib:
        fn_lib = fn_base + '-cache.lib'
    else:
        fn_lib = fn_base + '.lib'
    with open(fn_lib, "wt") as f:
        f.write(library.serialize_lib(cache_lib))
    if not cache_lib:
        fn_dcm = fn_base + '.dcm'
        with open(fn_dcm, "wt") as f:
            f.write(library.serialize_dcm())
    return 0


if __name__ == "__main__":
    sys.exit(main())