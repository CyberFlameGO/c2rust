'''This module generates `LuaAstNode` impls for each AST node.

Attributes:

- `#[fold_kind=FooKind]`: Folds the kind enum with the given name
  into the current structure.

- `#[to_lua_custom]`: implements `ToLuaExt` and `UserData` separately.
'''

from datetime import datetime
from textwrap import indent, dedent

from ast import *
from util import *

@linewise
def do_enum_variants(s, match_pat):
    # Emit `children`
    yield '    methods.add_method("children", |_lua_ctx, this, ()| {'
    yield '      match %s {' % match_pat
    for v in s.variants:
        fpat = struct_pattern(v, '%s::%s' % (s.name, v.name))
        yield '        %s => Ok([' % fpat
        for f in v.fields:
            yield '          %s.clone().to_lua_ext(_lua_ctx)?,' % f.name
        yield '        ].to_vec() as Vec<Value>),'
    yield '      }'
    yield '    });'

    # Emit `nth_child`
    yield '    methods.add_method("nth_child", |_lua_ctx, this, idx: usize| {'
    yield '      match (%s, idx) {' % match_pat
    for v in s.variants:
        for idx, f in enumerate(v.fields):
            fpat = struct_pattern(v, '%s::%s' % (s.name, v.name))
            yield '        (%s, %d) => %s.clone().to_lua_ext(_lua_ctx),' % (fpat, (idx + 1), f.name)
    yield '        _ => Ok(Value::Nil)' # FIXME
    yield '      }'
    yield '    });'

@linewise
def do_one_impl(s, kind_map, boxed):
    # This object is NOT thread-safe. Do not use an object of this class from a
    # thread that did not acquire it.
    type_name = 'P<%s>' % s.name if boxed else s.name
    yield 'unsafe impl Send for LuaAstNode<%s> {}' % type_name
    yield 'impl LuaAstNodeSafe for LuaAstNode<%s> {}' % type_name
    yield 'impl UserData for LuaAstNode<%s> {' % type_name
    yield '  #[allow(unused, non_shorthand_field_patterns)]'
    yield '  fn add_methods<\'lua, M: UserDataMethods<\'lua, Self>>(methods: &mut M) {'
    if isinstance(s, Struct):
        # FIXME: handle tuple struct
        kind_field = find_kind_field(s)
        for f in s.fields:
            yield '    methods.add_method("get_%s", |_lua_ctx, this, ()| {' % f.name
            if f.name == kind_field:
                yield '      Ok(this.borrow().%s.ast_name())' % f.name
            else:
                yield '      this.borrow().%s.clone().to_lua_ext(_lua_ctx)' % f.name
            yield '    });'

        if 'fold_kind' in s.attrs:
            kind_name = s.attrs['fold_kind']
            kind_decl = kind_map[kind_name]
            yield do_enum_variants(kind_decl, '&this.borrow().%s' % kind_field)

    elif isinstance(s, Enum):
        yield '    methods.add_method("get_kind", |_lua_ctx, this, ()| {'
        yield '      Ok(this.borrow().ast_name())'
        yield '    });'
        box_prefix = '&**' if boxed else '&*'
        yield do_enum_variants(s, box_prefix + 'this.borrow()')

    yield '    <Self as AddMoreMethods>::add_more_methods(methods);'
    yield '  }'
    yield '}'

@linewise
def do_impl(s, kind_map):
    if 'boxed' in s.attrs:
        yield do_one_impl(s, kind_map, True)
    if 'boxed' not in s.attrs or s.attrs['boxed'] == 'both':
        yield do_one_impl(s, kind_map, False)

@linewise
def generate(decls):
    yield '// AUTOMATICALLY GENERATED - DO NOT EDIT'
    yield '// Produced %s by process_ast.py' % (datetime.now(),)
    yield ''

    kind_map = {}
    for d in decls:
        if 'fold_kind' in d.attrs:
            kind_name = d.attrs['fold_kind']
            kind_map[kind_name] = None

    for d in decls:
        if d.name in kind_map:
            kind_map[d.name] = d

    for d in decls:
        if 'to_lua_custom' in d.attrs:
            continue

        yield do_impl(d, kind_map)
