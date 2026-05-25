import os
import ast
import chromadb

class RepoIndexer:
    def __init__(self, persist_dir: str = "./.chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(name="repo_code")

    def index_repo(self, repo_dir: str):
        print(f"Indexing repository at {repo_dir}...")
        documents = []
        metadatas = []
        ids = []

        for root, dirs, files in os.walk(repo_dir):
            if ".git" in root or "node_modules" in root or "__pycache__" in root:
                continue
            
            for file in files:
                if not file.endswith(".py") and not file.endswith((".js", ".jsx", ".ts", ".tsx", ".go")):
                    continue
                
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, repo_dir)
                try:
                    with open(filepath, "rb") as f:
                        content_bytes = f.read()
                    
                    extension = os.path.splitext(file)[1]
                    
                    import tree_sitter
                    from tree_sitter import Language, Parser
                    
                    parser = Parser()
                    if extension == ".py":
                        import tree_sitter_python as tspython
                        parser.language = Language(tspython.language())
                    elif extension in (".js", ".jsx"):
                        import tree_sitter_javascript as tsjavascript
                        parser.language = Language(tsjavascript.language())
                    elif extension in (".ts", ".tsx"):
                        import tree_sitter_typescript as tstypescript
                        parser.language = Language(tstypescript.language_typescript())
                    elif extension == ".go":
                        import tree_sitter_go as tsgo
                        parser.language = Language(tsgo.language())
                    else:
                        parser = None

                    if parser:
                        tree = parser.parse(content_bytes)
                        
                        def traverse(node):
                            if node.type in ("function_definition", "class_definition", "method_definition", "function_declaration", "method_declaration", "arrow_function"):
                                chunk_text = content_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
                                name = "unknown"
                                for child in node.children:
                                    if child.type in ("identifier", "name"):
                                        name = content_bytes[child.start_byte:child.end_byte].decode('utf-8')
                                        break
                                
                                documents.append(chunk_text)
                                metadatas.append({"file": rel_path, "type": node.type, "name": name})
                                ids.append(f"{rel_path}::{name}::{len(documents)}")
                            for child in node.children:
                                traverse(child)

                        traverse(tree.root_node)
                    else:
                        # Fallback for unsupported or generic files
                        content_str = content_bytes.decode("utf-8", errors="ignore")
                        chunk = content_str[:4000] 
                        documents.append(chunk)
                        metadatas.append({"file": rel_path, "type": "file", "name": file})
                        ids.append(f"{rel_path}::{len(documents)}")
                        
                except Exception as e:
                    print(f"Failed to index {rel_path}: {e}")

        if documents:
            # Upsert in batches of 100
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                self.collection.upsert(
                    documents=documents[i:i+batch_size],
                    metadatas=metadatas[i:i+batch_size],
                    ids=ids[i:i+batch_size]
                )
        print("Indexing complete.")

    def search(self, query: str, n_results: int = 3) -> str:
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            output = ""
            for i, doc in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                output += f"--- {meta['file']} ({meta['type']} {meta['name']}) ---\n{doc}\n\n"
            return output if output else "No results found."
        except Exception as e:
            return f"Search failed: {e}"
