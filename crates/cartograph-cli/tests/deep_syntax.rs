//! Regression test: the shipped binary survives a very deep syntax tree.
//!
//! `cartograph` aborted with a stack overflow on Windows while analysing
//! `PostHog` at the benchmark corpus commit. Two files declare TypeScript unions
//! of about 1,300 members, which tree-sitter nests 1,300 levels deep, and the
//! extractors walked the tree recursively. Windows gives the main thread 1 MiB
//! of stack; the walk needed more than 1.5 MiB.
//!
//! The parser crate's own tests reproduce that on a thread sized like Windows'
//! main thread. This one runs the real executable, so on Windows it exercises
//! the main thread that actually overflowed, and everywhere else its depth is
//! chosen to exceed an 8 MiB main-thread stack under the recursive walk too.

use std::path::PathBuf;
use std::process::Command;

fn cartograph() -> Command {
    Command::new(env!("CARGO_BIN_EXE_cartograph"))
}

/// Far deeper than `PostHog`'s 1,303 nested unions.
const MEMBERS: usize = 20_000;

/// A throwaway repository, removed when the test finishes.
struct Repository {
    root: PathBuf,
}

impl Repository {
    fn with_deep_union() -> Self {
        let root = std::env::temp_dir().join(format!(
            "cartograph-deep-syntax-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).expect("create");
        let union: Vec<String> = (0..MEMBERS).map(|i| format!("'k{i}'")).collect();
        std::fs::write(
            root.join("catalog.ts"),
            format!(
                "export type SourceKind = {};\n\
                 export function loadSources() {{\n  return fetch('/api/sources');\n}}\n",
                union.join(" | ")
            ),
        )
        .expect("write");
        Self { root }
    }
}

impl Drop for Repository {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.root);
    }
}

#[test]
fn parse_completes_on_a_union_twenty_thousand_members_deep() {
    let repository = Repository::with_deep_union();
    let output = cartograph()
        .args(["parse", "--json"])
        .arg(&repository.root)
        .output()
        .expect("binary runs");

    assert!(
        output.status.success(),
        "exit status {}; stderr: {}",
        output.status,
        String::from_utf8_lossy(&output.stderr)
    );
    let value: serde_json::Value = serde_json::from_slice(&output.stdout).expect("JSON");
    let file = &value["files"][0];
    let symbols: Vec<&str> = file["symbols"]
        .as_array()
        .expect("symbols")
        .iter()
        .filter_map(|s| s["name"].as_str())
        .collect();
    assert_eq!(symbols, ["SourceKind", "loadSources"]);
    assert_eq!(file["http_calls"].as_array().expect("calls").len(), 1);
}

#[test]
fn match_completes_on_a_union_twenty_thousand_members_deep() {
    // `match` is the command the benchmark runs, and it reaches the resolver.
    let repository = Repository::with_deep_union();
    let output = cartograph()
        .args(["match", "--json"])
        .arg(&repository.root)
        .output()
        .expect("binary runs");

    assert!(
        output.status.success(),
        "exit status {}; stderr: {}",
        output.status,
        String::from_utf8_lossy(&output.stderr)
    );
    let value: serde_json::Value = serde_json::from_slice(&output.stdout).expect("JSON");
    assert_eq!(value["totals"]["files"], 1);
    assert_eq!(value["totals"]["client_calls"], 1);
}
