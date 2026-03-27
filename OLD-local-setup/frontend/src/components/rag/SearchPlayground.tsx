import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search, Loader2, Database, Star } from "lucide-react";
import { search } from "@/api/rag";
import type { SearchResult, Collection } from "@/types/rag";

interface SearchPlaygroundProps {
  collections: Collection[];
}

export default function SearchPlayground({
  collections,
}: SearchPlaygroundProps) {
  const [query, setQuery] = useState("");
  const [selectedCollections, setSelectedCollections] = useState<string[]>([]);
  const [topK, setTopK] = useState(5);
  const [minScore, setMinScore] = useState(0.5);
  const [results, setResults] = useState<SearchResult[]>([]);

  const searchMutation = useMutation({
    mutationFn: () =>
      search({
        query,
        collections:
          selectedCollections.length > 0 ? selectedCollections : undefined,
        topK,
        minScore,
      }),
    onSuccess: (data) => setResults(data),
  });

  function handleSearch() {
    if (!query.trim()) return;
    searchMutation.mutate();
  }

  function toggleCollection(name: string) {
    setSelectedCollections((prev) =>
      prev.includes(name)
        ? prev.filter((c) => c !== name)
        : [...prev, name]
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
        Search Playground
      </h3>

      {/* Search input */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Enter a semantic search query..."
            className="input pl-9"
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={searchMutation.isPending || !query.trim()}
          className="btn-primary"
        >
          {searchMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          Search
        </button>
      </div>

      {/* Filters row */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Collection filter */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-gray-500 dark:text-gray-400">
            Collections:
          </span>
          {collections.map((col) => (
            <button
              key={col.id}
              onClick={() => toggleCollection(col.name)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                selectedCollections.includes(col.name)
                  ? "bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300"
              }`}
            >
              {col.name}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500 dark:text-gray-400">
            Top K:
          </label>
          <input
            type="number"
            value={topK}
            onChange={(e) => setTopK(parseInt(e.target.value) || 5)}
            min={1}
            max={20}
            className="input w-16"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500 dark:text-gray-400">
            Min Score:
          </label>
          <input
            type="number"
            value={minScore}
            onChange={(e) => setMinScore(parseFloat(e.target.value) || 0)}
            min={0}
            max={1}
            step={0.1}
            className="input w-20"
          />
        </div>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {results.length} results found
          </p>
          {results.map((result, idx) => (
            <div
              key={result.id || idx}
              className="rounded-lg border border-gray-200 bg-white p-4 transition-colors hover:border-brand-200 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-brand-700"
            >
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-brand-500" />
                  <span className="text-sm font-medium text-brand-600 dark:text-brand-400">
                    {result.collection}
                  </span>
                  <span className="text-xs text-gray-400">
                    Chunk #{result.chunkIndex}
                  </span>
                </div>
                <span className="flex items-center gap-1 text-sm font-medium">
                  <Star className="h-3.5 w-3.5 text-amber-400" />
                  {result.score.toFixed(4)}
                </span>
              </div>

              <p className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
                {result.content}
              </p>

              {Object.keys(result.metadata).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {Object.entries(result.metadata).map(([key, value]) => (
                    <span
                      key={key}
                      className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500 dark:bg-gray-700 dark:text-gray-400"
                    >
                      {key}: {String(value)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {searchMutation.isSuccess && results.length === 0 && (
        <div className="rounded-lg bg-gray-50 py-8 text-center dark:bg-gray-800/50">
          <Search className="mx-auto h-8 w-8 text-gray-300 dark:text-gray-600" />
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            No results found. Try a different query or lower the minimum score.
          </p>
        </div>
      )}
    </div>
  );
}
