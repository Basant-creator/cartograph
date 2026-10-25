//! Regression tests: syntax-tree depth must not cost native stack.
//!
//! The extractors walked the tree recursively, one stack frame per level. A
//! flat-looking list can be thousands of levels deep, because tree-sitter
//! nests binary constructs: `'a' | 'b' | 'c'` is
//! `union_type(union_type('a', 'b'), 'c')`. `PostHog`'s data-warehouse source
//! catalog (`sourceCatalogLogic.ts` and `sourceWizardLogic.tsx`, at the
//! benchmark corpus commit) declares unions of about 1,300 members, a named
//! depth of 1,321. The walk needed more than 1.5 MiB of stack to finish them.
//! Windows gives the main thread 1 MiB, so `cartograph` aborted there with a
//! stack overflow, and analysing that repository was impossible.
//!
//! Each test builds a minimized input of that shape, several times deeper
//! than `PostHog`'s, and analyses it on a thread whose stack is exactly the
//! Windows main-thread default. A recursive walk aborts the whole test binary;
//! the walk is now iterative, so depth costs heap, not stack. Each test also
//! checks what was extracted *after* the deep subtree, because surviving the
//! walk is not the same as completing it.

use cartograph_parser::Analyzer;
use cartograph_parser::model::{FileAnalysis, StringFact, SymbolKind, UrlObservation};

/// Windows' default main-thread stack: the stack `cartograph` itself runs on.
const WINDOWS_MAIN_THREAD_STACK: usize = 1024 * 1024;

/// Several times `PostHog`'s 1,303 nested unions, so the margin is not thin.
const DEPTH: usize = 5_000;

fn analyze_on_windows_sized_stack(path: &str, source: String) -> FileAnalysis {
    let path = path.to_owned();
    std::thread::Builder::new()
        .stack_size(WINDOWS_MAIN_THREAD_STACK)
        .spawn(move || {
            Analyzer::new()
                .expect("grammars load")
                .analyze_source(&path, &source)
                .expect("supported path")
        })
        .expect("thread spawns")
        .join()
        .expect("analysis completes on a 1 MiB stack")
}

/// `export type SourceKind = 'k0' | 'k1' | …;` followed by a function that
/// makes a request — the shape of `PostHog`'s catalog, minimized.
fn union_then_request(members: usize) -> String {
    let union: Vec<String> = (0..members).map(|i| format!("'k{i}'")).collect();
    format!(
        "export type SourceKind = {};\n\
         export function loadSources() {{\n  return fetch('/api/sources');\n}}\n",
        union.join(" | ")
    )
}

fn request_urls(analysis: &FileAnalysis) -> Vec<(String, Option<String>)> {
    analysis
        .http_calls
        .iter()
        .map(|call| {
            let url = match &call.url {
                UrlObservation::Literal { value } => value.clone(),
                other => format!("{other:?}"),
            };
            (url, call.enclosing.clone())
        })
        .collect()
}

fn symbol_kind(analysis: &FileAnalysis, name: &str) -> SymbolKind {
    analysis
        .symbols
        .iter()
        .find(|s| s.name == name)
        .unwrap_or_else(|| panic!("no symbol {name}"))
        .kind
}

// ── TypeScript ──────────────────────────────────────────────────────

#[test]
fn a_typescript_union_thousands_of_members_deep_is_walked_without_overflow() {
    let analysis = analyze_on_windows_sized_stack("catalog.ts", union_then_request(DEPTH));

    assert_eq!(symbol_kind(&analysis, "SourceKind"), SymbolKind::TypeAlias);
    assert_eq!(symbol_kind(&analysis, "loadSources"), SymbolKind::Function);
    // The walk reached the function after the union, inside its scope.
    assert_eq!(
        request_urls(&analysis),
        vec![("/api/sources".to_owned(), Some("loadSources".to_owned()))]
    );
    // Every member was visited: each is a string literal fact, in order.
    let literals: Vec<&str> = analysis
        .strings
        .iter()
        .filter_map(|s| match s {
            StringFact::Literal { value, .. } => Some(value.as_str()),
            _ => None,
        })
        .collect();
    assert_eq!(literals.len(), DEPTH + 1, "every member, then the URL");
    assert_eq!(literals[0], "k0");
    assert_eq!(literals[DEPTH - 1], format!("k{}", DEPTH - 1));
    assert_eq!(literals[DEPTH], "/api/sources");
}

#[test]
fn a_tsx_union_thousands_of_members_deep_is_walked_without_overflow() {
    // `sourceWizardLogic.tsx` is the TSX half of the PostHog crash; TSX is
    // a separate grammar, so it is covered separately.
    let analysis = analyze_on_windows_sized_stack("wizard.tsx", union_then_request(DEPTH));

    assert_eq!(symbol_kind(&analysis, "SourceKind"), SymbolKind::TypeAlias);
    assert_eq!(
        request_urls(&analysis),
        vec![("/api/sources".to_owned(), Some("loadSources".to_owned()))]
    );
}

#[test]
fn a_typescript_concatenation_thousands_of_operands_long_is_one_fact_in_order() {
    // `a + b + c` nests the same way, and it is flattened by its own walk.
    let operands: Vec<String> = (0..DEPTH)
        .map(|i| {
            if i % 2 == 0 {
                format!("'s{i}'")
            } else {
                format!("v{i}")
            }
        })
        .collect();
    let source = format!("const url = {};\n", operands.join(" + "));
    let analysis = analyze_on_windows_sized_stack("concat.ts", source);

    let concatenations: Vec<_> = analysis
        .strings
        .iter()
        .filter_map(|s| match s {
            StringFact::Concatenation { parts, .. } => Some(parts),
            _ => None,
        })
        .collect();
    assert_eq!(concatenations.len(), 1, "one chain, one fact");
    let parts = concatenations[0];
    assert_eq!(parts.len(), DEPTH);
    assert_eq!(format!("{:?}", parts[0]), r#"Literal { value: "s0" }"#);
    assert_eq!(format!("{:?}", parts[1]), r#"Expression { source: "v1" }"#);
    assert_eq!(
        format!("{:?}", parts[DEPTH - 1]),
        format!(r#"Expression {{ source: "v{}" }}"#, DEPTH - 1)
    );
}

// ── Python ──────────────────────────────────────────────────────────

#[test]
fn a_python_boolean_chain_thousands_of_operands_deep_is_walked_without_overflow() {
    // The Python extractor walked the same way. `a or b or c` nests like a
    // TypeScript union, and so does `A | B | C` in a type hint.
    let operands: Vec<String> = (0..DEPTH).map(|i| format!("flag{i}")).collect();
    let source = format!(
        "ENABLED = {}\n\n\
         def load_sources():\n    return requests.get(\"/api/sources\")\n",
        operands.join(" or ")
    );
    let analysis = analyze_on_windows_sized_stack("catalog.py", source);

    assert_eq!(symbol_kind(&analysis, "load_sources"), SymbolKind::Function);
    assert_eq!(
        request_urls(&analysis),
        vec![("/api/sources".to_owned(), Some("load_sources".to_owned()))]
    );
}

#[test]
fn a_python_concatenation_thousands_of_operands_long_is_one_fact_in_order() {
    let operands: Vec<String> = (0..DEPTH)
        .map(|i| {
            if i % 2 == 0 {
                format!("\"s{i}\"")
            } else {
                format!("v{i}")
            }
        })
        .collect();
    let source = format!("URL = {}\n", operands.join(" + "));
    let analysis = analyze_on_windows_sized_stack("concat.py", source);

    let concatenations: Vec<_> = analysis
        .strings
        .iter()
        .filter_map(|s| match s {
            StringFact::Concatenation { parts, .. } => Some(parts),
            _ => None,
        })
        .collect();
    assert_eq!(concatenations.len(), 1, "one chain, one fact");
    let parts = concatenations[0];
    assert_eq!(parts.len(), DEPTH);
    assert_eq!(format!("{:?}", parts[0]), r#"Literal { value: "s0" }"#);
    assert_eq!(
        format!("{:?}", parts[DEPTH - 1]),
        format!(r#"Expression {{ source: "v{}" }}"#, DEPTH - 1)
    );
}
