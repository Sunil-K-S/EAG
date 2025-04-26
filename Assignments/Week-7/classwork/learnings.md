# Week 7 - Embeddings and Task Types Learnings

## Table of Contents
1. [Core Concepts and Fundamentals](#core-concepts-and-fundamentals)
2. [Implementation Details and Code Examples](#implementation-details-and-code-examples)
3. [FAISS Deep Dive](#faiss-deep-dive)
4. [Error Handling and Best Practices](#error-handling-and-best-practices)
5. [Advanced Topics and Future Considerations](#advanced-topics-and-future-considerations)

## Core Concepts and Fundamentals

### 1. Embeddings
- Embeddings are numerical representations of text that capture semantic meaning
- Google's Generative AI provides different embedding models for various tasks
- We used the `gemini-embedding-exp-03-07` model in our experiments

### 2. Task Types
We explored three main task types:

#### CLUSTERING
- Purpose: Best for grouping similar items together
- Use Case: When you need to organize similar content into groups
- Example: Grouping similar documents or texts

#### RETRIEVAL_DOCUMENT
- Purpose: Best for finding relevant documents
- Use Case: Search and information retrieval
- Example: Finding relevant answers to questions

#### SEMANTIC_SIMILARITY
- Purpose: Best for measuring text similarity
- Use Case: Comparing how similar two pieces of text are
- Example: Detecting paraphrases or similar content

### 3. Cosine Similarity
- Definition: A measure of similarity between two vectors
- Formula: `cosine_similarity = (A · B) / (||A|| * ||B||)`
- Range: -1 to 1
  - 1: Identical vectors
  - 0: Orthogonal vectors
  - -1: Opposite vectors
- Importance:
  - Measures semantic similarity between texts
  - Independent of vector magnitude
  - Efficient for high-dimensional vectors
  - Normalizes for different text lengths

## Implementation Details and Code Examples

### 1. Basic Implementation
```python
def get_embedding(text: str, task_type: str, max_retries=3) -> np.ndarray:
    """Get embedding for text using specified task type with retry logic"""
    for attempt in range(max_retries):
        try:
            result = genai.embed_content(
                model="models/gemini-embedding-exp-03-07",
                content=text,
                task_type=task_type
            )
            return np.array(result['embedding'], dtype=np.float32)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            time.sleep(5)

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

### 2. Progress Tracking
```python
# Progress tracking files
PROGRESS_FILE = "faiss_progress.pkl"  # For embeddings
METADATA_FILE = "faiss_metadata.json"  # For document metadata

def save_progress(chunks, metadata):
    """Save current progress to disk"""
    try:
        with open(PROGRESS_FILE, 'wb') as f:
            pickle.dump(chunks, f)
        with open(METADATA_FILE, 'w') as f:
            json.dump(metadata, f)
        print("💾 Progress saved successfully")
    except Exception as e:
        print(f"⚠️ Could not save progress: {e}")

def load_progress():
    """Load progress from disk if available"""
    try:
        if os.path.exists(PROGRESS_FILE) and os.path.exists(METADATA_FILE):
            with open(PROGRESS_FILE, 'rb') as f:
                chunks = pickle.load(f)
            with open(METADATA_FILE, 'r') as f:
                metadata = json.load(f)
            print(f"📂 Loaded {len(chunks)} previously processed chunks")
            return chunks, metadata
    except Exception as e:
        print(f"⚠️ Could not load progress: {e}")
    return [], []
```

### 3. Quota Management
```python
# Quota management variables
QUOTA_RESET_TIME = None
QUOTA_EXHAUSTED = False
MIN_WAIT_TIME = 60  # Minimum wait time in seconds
MAX_WAIT_TIME = 300  # Maximum wait time in seconds
current_wait_time = MIN_WAIT_TIME

def check_quota_status() -> bool:
    """Check if we should wait due to quota exhaustion"""
    global QUOTA_RESET_TIME, QUOTA_EXHAUSTED, current_wait_time
    
    if not QUOTA_EXHAUSTED:
        return True
        
    if QUOTA_RESET_TIME and datetime.now() < QUOTA_RESET_TIME:
        wait_seconds = (QUOTA_RESET_TIME - datetime.now()).total_seconds()
        print(f"⏳ Quota exhausted. Waiting {wait_seconds:.0f} seconds until reset...")
        time.sleep(wait_seconds)
        QUOTA_EXHAUSTED = False
        QUOTA_RESET_TIME = None
        current_wait_time = MIN_WAIT_TIME
        return True
        
    return False
```

## FAISS Deep Dive

### 1. Core Components
- Takes vectors (embeddings) as input
- Builds an index structure for efficient search
- Returns nearest neighbors for queries

### 2. Data Flow and Processing
```python
# Input Processing
embeddings = [vector1, vector2, ...]  # List of vectors
dimension = len(embeddings[0])        # Get vector dimension

# Index Creation
index = faiss.IndexFlatL2(dimension)  # Create index
index.add(np.stack(embeddings))       # Add vectors to index

# Query Processing
query_vector = get_embedding("query text")
query_vector = query_vector.reshape(1, -1)

# Search and Results
D, I = index.search(query_vector, k=3)  # Get top 3 matches
```

### 3. Input/Output Specifications
- **Vectors to Index**:
  - Type: numpy array
  - Shape: (n_vectors, vector_dimension)
  - Example: `[[0.1, 0.2, ...], [0.3, 0.4, ...]]`
- **Query Vector**:
  - Type: numpy array
  - Shape: (1, vector_dimension)
  - Must match dimension of indexed vectors
- **k (neighbors)**:
  - Number of nearest neighbors to return
  - Affects search time and memory usage

### 4. Distance Metrics
- **L2 (Euclidean) Distance**:
  - `IndexFlatL2`: Standard Euclidean distance
  - Good for general similarity search
  - Formula: √(Σ(xᵢ - yᵢ)²)
- **Inner Product**:
  - `IndexFlatIP`: Dot product similarity
  - Good for normalized vectors
  - Formula: Σ(xᵢ * yᵢ)
- **Cosine Similarity**:
  - Implemented using normalized vectors with IP
  - Formula: (x·y)/(||x||*||y||)

### 5. Index Types and Use Cases
- **Flat Index** (`IndexFlatL2`):
  - Brute-force search
  - Exact results
  - Best for: Small datasets, exact matches
- **IVF Index** (`IndexIVFFlat`):
  - Inverted file with clustering
  - Approximate results
  - Best for: Medium to large datasets
- **HNSW Index** (`IndexHNSW`):
  - Hierarchical Navigable Small World
  - Very fast search
  - Best for: High-dimensional data

## Error Handling and Best Practices

### 1. Rate Limiting and Quota Management
- Implement exponential backoff
- Add jitter to prevent synchronized retries
- Monitor quota usage
- Handle partial task completion gracefully

### 2. Error Recovery
```python
try:
    result = client.models.embed_content(...)
except Exception as e:
    if attempt == max_retries - 1:
        print(f"❌ Failed after {max_retries} attempts: {e}")
        raise
    print(f"⚠️ Attempt {attempt + 1} failed: {str(e)}")
    time.sleep(5 * (attempt + 1))
```

### 3. Progress Tracking Best Practices
1. Save progress after each file
2. Save progress on errors
3. Use appropriate file formats
4. Provide clear feedback
5. Handle errors gracefully
6. Track processed files
7. Skip already processed content
8. Maintain metadata integrity

### 4. Common Pitfalls
- Mismatched vector dimensions
- Unnormalized vectors with IP/Cosine
- Insufficient memory for large indices
- Poor choice of index type
- Not considering search speed vs. accuracy trade-offs
- Forgetting to reshape query vectors
- Not handling API rate limits properly
- Ignoring memory constraints with large datasets

## Advanced Topics and Future Considerations

### 1. Text Chunking Strategies
- Word-based chunking with overlap
- Sentence-based chunking
- Paragraph-based chunking
- Content-aware chunking

### 2. Performance Optimization
- GPU acceleration
- Batch processing
- Caching strategies
- Memory management

### 3. Future Enhancements
1. Experiment with different embedding models
2. Explore more complex similarity metrics
3. Implement batch processing for large datasets
4. Add visualization of embedding spaces
5. Consider hybrid approaches combining multiple task types
6. Explore different FAISS index types for specific use cases
7. Implement caching for frequently accessed embeddings
8. Add support for incremental updates to the index
9. Consider distributed search for very large datasets
10. Add support for filtering by metadata during search

### 4. Ollama Integration
- Local LLM models
- API integration
- Advantages and limitations
- Use cases and best practices

### 5. System Monitoring
- Performance metrics
- Error tracking
- Resource usage
- API monitoring

## Queries and Solutions

### 1. Initial Error Resolution
- Problem: `AttributeError` when initializing the Gemini client
- Solution: Corrected client initialization and embedding generation method

### 2. Rate Limiting
- Problem: API rate limits affecting script execution
- Solution: Implemented retry logic and error handling
- Implementation:
  - Added delay between API calls
  - Implemented exponential backoff
  - Added maximum retry attempts

### 3. Task Type Comparison
- Explored differences between task types using various text pairs
- Implemented systematic comparison framework
- Analyzed similarity scores for different scenarios

## Best Practices
1. Always implement retry logic for API calls
2. Use appropriate delays between API requests
3. Normalize embeddings before comparison
4. Choose the right task type for your specific use case
5. Document and analyze similarity thresholds for your application
6. Implement rate limit checking and handling:
   - Use exponential backoff with jitter
   - Check rate limits before making full requests
   - Implement progressive wait times
   - Add random jitter to prevent thundering herd

## Rate Limit Handling
### Strategies for Managing API Rate Limits
1. **Pre-emptive Checks**
   - Make minimal test calls to check availability
   - Monitor rate limit headers if available
   - Implement health check endpoints

2. **Retry Mechanisms**
   - Exponential backoff: Increase wait time with each retry
   - Jitter: Add random variation to prevent synchronized retries
   - Maximum retry attempts: Prevent infinite loops

3. **Implementation Example**
```python
def check_rate_limit(task_type: str) -> bool:
    """Check if we can make an API call based on rate limits"""
    try:
        result = genai.embed_content(
            model="models/gemini-embedding-exp-03-07",
            content="test",
            task_type=task_type
        )
        return True
    except Exception as e:
        if "rate limit" in str(e).lower():
            return False
        return True
```

4. **Best Practices for Rate Limiting**
   - Monitor API responses for rate limit headers
   - Implement circuit breakers for repeated failures
   - Use appropriate backoff strategies
   - Log rate limit events for monitoring
   - Consider implementing a rate limit queue

## Rate Limit and Quota Management
### Strategies for Managing API Limits
1. **Quota Management**
   - Track quota exhaustion status globally
   - Implement reset period tracking
   - Gracefully handle partial task completion
   - Provide clear feedback about wait times

2. **Implementation Example**
```python
# Global variables for quota management
QUOTA_RESET_TIME = None
QUOTA_EXHAUSTED = False

def check_quota_status() -> bool:
    """Check if we should wait due to quota exhaustion"""
    global QUOTA_RESET_TIME, QUOTA_EXHAUSTED
    
    if not QUOTA_EXHAUSTED:
        return True
        
    if QUOTA_RESET_TIME and datetime.now() < QUOTA_RESET_TIME:
        wait_seconds = (QUOTA_RESET_TIME - datetime.now()).total_seconds()
        print(f"Quota exhausted. Waiting {wait_seconds:.0f} seconds until reset...")
        time.sleep(wait_seconds)
        QUOTA_EXHAUSTED = False
        QUOTA_RESET_TIME = None
        return True
        
    return False
```

3. **Best Practices for Quota Management**
   - Implement proper reset period tracking
   - Use global state for quota status
   - Gracefully handle partial task completion
   - Provide clear user feedback
   - Consider implementing a queue system for large batches

## Vector Search with FAISS
### Key Learnings from FAISS Implementation

1. **Vector Search Basics**
   - FAISS (Facebook AI Similarity Search) is a library for efficient similarity search
   - Works with high-dimensional vectors (like embeddings)
   - Provides fast nearest neighbor search capabilities

2. **Implementation Components**
   ```python
   # Create FAISS index
   dimension = len(embeddings[0])
   index = faiss.IndexFlatL2(dimension)
   index.add(np.stack(embeddings))

   # Search
   D, I = index.search(query_vector, k=3)  # k=3 for top 3 matches
   ```
   - `IndexFlatL2`: Uses L2 (Euclidean) distance for similarity
   - `np.stack()`: Combines embeddings into a single array
   - Search returns distances (D) and indices (I)

3. **Best Practices**
   - Pre-compute embeddings for your corpus
   - Store metadata separately from embeddings
   - Use appropriate distance metric (L2 for embeddings)
   - Implement proper error handling for API calls
   - Add delays between API calls to manage rate limits

4. **Quota Management in Production**
   - Implement global quota tracking
   - Use exponential backoff for retries
   - Add jitter to prevent thundering herd
   - Track reset periods
   - Gracefully handle partial completion

5. **Use Case Example (Joke Search)**
   - Store jokes with metadata (ID, category, text)
   - Generate embeddings for each joke
   - Create FAISS index for efficient search
   - Map indices back to original metadata
   - Return top-k most similar jokes

6. **Performance Considerations**
   - FAISS is optimized for large-scale vector search
   - Supports both CPU and GPU implementations
   - Various index types for different use cases
   - Memory-efficient storage of vectors
   - Fast query response times

7. **Integration with Embedding APIs**
   - Handle API rate limits gracefully
   - Implement proper error handling
   - Cache embeddings when possible
   - Use appropriate task types for embeddings
   - Monitor API usage and quotas

## FAISS Mechanics and Implementation
### How FAISS Works

1. **Core Components**
   - Takes vectors (embeddings) as input
   - Builds an index structure for efficient search
   - Returns nearest neighbors for queries

2. **Data Flow and Processing**
   ```python
   # Input Processing
   embeddings = [vector1, vector2, ...]  # List of vectors
   dimension = len(embeddings[0])        # Get vector dimension
   
   # Index Creation
   index = faiss.IndexFlatL2(dimension)  # Create index
   index.add(np.stack(embeddings))       # Add vectors to index
   
   # Query Processing
   query_vector = get_embedding("query text")
   query_vector = query_vector.reshape(1, -1)
   
   # Search and Results
   D, I = index.search(query_vector, k=3)  # Get top 3 matches
   ```

3. **Input Specifications**
   - **Vectors to Index**:
     - Type: numpy array
     - Shape: (n_vectors, vector_dimension)
     - Example: `[[0.1, 0.2, ...], [0.3, 0.4, ...]]`
   - **Query Vector**:
     - Type: numpy array
     - Shape: (1, vector_dimension)
     - Must match dimension of indexed vectors
   - **k (neighbors)**:
     - Number of nearest neighbors to return
     - Affects search time and memory usage

4. **Output Specifications**
   - **D (Distances)**:
     - Type: numpy array
     - Shape: (n_queries, k)
     - Contains distances to nearest neighbors
     - Lower distance = more similar
   - **I (Indices)**:
     - Type: numpy array
     - Shape: (n_queries, k)
     - Contains indices of nearest neighbors
     - Maps back to original vectors

5. **Distance Metrics**
   - **L2 (Euclidean) Distance**:
     - `IndexFlatL2`: Standard Euclidean distance
     - Good for general similarity search
     - Formula: √(Σ(xᵢ - yᵢ)²)
   - **Inner Product**:
     - `IndexFlatIP`: Dot product similarity
     - Good for normalized vectors
     - Formula: Σ(xᵢ * yᵢ)
   - **Cosine Similarity**:
     - Implemented using normalized vectors with IP
     - Formula: (x·y)/(||x||*||y||)

6. **Index Types and Use Cases**
   - **Flat Index** (`IndexFlatL2`):
     - Brute-force search
     - Exact results
     - Best for: Small datasets, exact matches
   - **IVF Index** (`IndexIVFFlat`):
     - Inverted file with clustering
     - Approximate results
     - Best for: Medium to large datasets
   - **HNSW Index** (`IndexHNSW`):
     - Hierarchical Navigable Small World
     - Very fast search
     - Best for: High-dimensional data

7. **Memory and Performance**
   - Memory Usage:
     - Vectors stored in memory
     - Index structures add overhead
     - Can handle billions of vectors
   - Performance Factors:
     - Vector dimension
     - Number of vectors
     - Index type
     - Hardware (CPU/GPU)
   - Optimization Tips:
     - Choose appropriate index type
     - Use GPU when available
     - Consider approximate search for large datasets

8. **Practical Implementation Notes**
   - Always check vector dimensions match
   - Normalize vectors when using IP/Cosine
   - Handle memory constraints for large datasets
   - Consider batch processing for large queries
   - Implement proper error handling
   - Monitor search performance

9. **Common Pitfalls**
   - Mismatched vector dimensions
   - Unnormalized vectors with IP/Cosine
   - Insufficient memory for large indices
   - Poor choice of index type
   - Not considering search speed vs. accuracy trade-offs

## Future Considerations
1. Experiment with different embedding models
2. Explore more complex similarity metrics
3. Implement batch processing for large datasets
4. Add visualization of embedding spaces
5. Consider hybrid approaches combining multiple task types
6. Explore different FAISS index types for specific use cases
7. Implement caching for frequently accessed embeddings
8. Add support for incremental updates to the index
9. Consider distributed search for very large datasets
10. Add support for filtering by metadata during search

## FAISS Practical Example: Joke Search System

### 1. Input Data (Our Jokes)
```python
jokes = [
    {"id": 1, "text": "Why don't cows have any money? Because farmers milk them dry."},
    {"id": 2, "text": "Why do programmers prefer dark mode? Because light attracts bugs."},
    {"id": 3, "text": "Why did the student eat his homework? Because the teacher said it was a piece of cake."}
]
```

### 2. Step-by-Step Process

1. **Generate Embeddings**
   - Each joke text is converted to a vector
   - Example: "Why don't cows have any money?" → [0.1, 0.2, 0.3, ...] (768 dimensions)
   - All jokes are converted to their vector representations

2. **Create FAISS Index**
   ```python
   # Stack all joke embeddings into a matrix
   # Shape: (3 jokes, 768 dimensions)
   embeddings = [
       [0.1, 0.2, ...],  # Joke 1 embedding
       [0.3, 0.4, ...],  # Joke 2 embedding
       [0.5, 0.6, ...]   # Joke 3 embedding
   ]
   
   # Create and populate index
   dimension = 768  # Dimension of our embeddings
   index = faiss.IndexFlatL2(dimension)
   index.add(np.stack(embeddings))
   ```

3. **Query Processing**
   ```python
   # User query: "Tell me a joke about coding"
   query_text = "Tell me a joke about coding"
   
   # Convert query to embedding
   query_vector = get_embedding(query_text)  # [0.7, 0.8, ...]
   query_vector = query_vector.reshape(1, -1)  # Shape: (1, 768)
   
   # Search for top 2 similar jokes
   D, I = index.search(query_vector, k=2)
   
   # Results:
   # D = [[0.1, 0.3]]  # Distances to top 2 matches
   # I = [[1, 2]]      # Indices of top 2 matches
   ```

4. **Result Interpretation**
   - `D[0][0] = 0.1`: Distance to most similar joke (Joke 2)
   - `I[0][0] = 1`: Index of most similar joke
   - Retrieved joke: "Why do programmers prefer dark mode? Because light attracts bugs."

### 3. Why This Works
- Joke 2 is about programming (matches query about coding)
- FAISS found it because its embedding is closest to the query embedding
- Lower distance (0.1) means higher semantic similarity
- The system returned the most contextually relevant joke

### 4. Real-World Analogy
Think of FAISS like a librarian:
1. **Index Creation**: Librarian organizes books (jokes) by topic
2. **Query**: You ask for "books about coding"
3. **Search**: Librarian finds books in the coding section
4. **Results**: Returns the most relevant books (jokes)

### 5. Key Benefits
- Fast search even with millions of jokes
- Semantic understanding of joke content
- Efficient memory usage
- Scalable to large datasets

### 6. Understanding Reshaping in FAISS

#### Why Reshape is Necessary
1. **Input Format Requirements**
   - FAISS expects query vectors in shape (n_queries, vector_dimension)
   - Single query needs shape (1, vector_dimension)
   - Raw embedding from API is typically shape (vector_dimension,)

2. **Example Without Reshape**
   ```python
   # Original embedding from API
   query_vector = get_embedding("Tell me a joke about coding")
   print(query_vector.shape)  # Output: (768,) - This won't work with FAISS
   
   # FAISS will raise error: "query vectors must be 2D"
   D, I = index.search(query_vector, k=2)  # Error!
   ```

3. **Correct Shape Example**
   ```python
   # After reshaping
   query_vector = query_vector.reshape(1, -1)
   print(query_vector.shape)  # Output: (1, 768) - This works!
   
   # Now FAISS can process it correctly
   D, I = index.search(query_vector, k=2)  # Success!
   ```

4. **Why This Matters**
   - FAISS is designed to handle batch queries
   - Shape (n_queries, vector_dimension) allows:
     - Single query: (1, 768)
     - Multiple queries: (n, 768)
   - Consistent shape makes processing efficient

5. **Real-World Analogy**
   - Think of it like organizing a stack of papers:
     - Without reshape: Single sheet lying flat
     - With reshape: Sheet properly stacked in a pile
     - FAISS needs the "stacked" format to process efficiently

### 7. Key Benefits
- Fast search even with millions of jokes
- Semantic understanding of joke content
- Efficient memory usage
- Scalable to large datasets

## Important Learnings Log

### 1. FAISS Implementation Learnings
- **Reshaping is Critical**: Always reshape query vectors to (n_queries, vector_dimension) format
  - Raw embeddings come as (vector_dimension,)
  - FAISS requires (n_queries, vector_dimension)
  - Use `reshape(1, -1)` for single queries
  - Use `reshape(n, -1)` for batch queries

- **Index Types Matter**:
  - `IndexFlatL2`: Exact search, good for small datasets
  - `IndexIVFFlat`: Approximate search, good for medium datasets
  - `IndexHNSW`: Fast approximate search, good for large datasets

- **Memory Management**:
  - FAISS indices are memory-intensive
  - Consider using GPU for large datasets
  - Can save/load indices to disk
  - Monitor memory usage with large vector collections

### 2. Embedding API Learnings
- **Task Types**:
  - `CLUSTERING`: Best for grouping similar items
  - `RETRIEVAL_DOCUMENT`: Best for document search
  - `SEMANTIC_SIMILARITY`: Best for text similarity comparison

- **Rate Limiting**:
  - Implement exponential backoff
  - Add jitter to prevent synchronized retries
  - Monitor quota usage
  - Handle partial task completion gracefully

### 3. Vector Search Best Practices
- **Pre-processing**:
  - Normalize vectors when using cosine similarity
  - Ensure consistent vector dimensions
  - Validate input data before indexing

- **Query Optimization**:
  - Batch queries when possible
  - Use appropriate k value for nearest neighbors
  - Consider approximate search for large datasets

- **Error Handling**:
  - Check vector dimensions match
  - Handle API rate limits
  - Implement proper retry logic
  - Log search performance metrics

### 4. Performance Considerations
- **Index Building**:
  - Pre-compute embeddings when possible
  - Choose appropriate index type for dataset size
  - Consider trade-off between speed and accuracy

- **Search Optimization**:
  - Use GPU acceleration for large datasets
  - Implement caching for frequent queries
  - Monitor search latency
  - Consider distributed search for very large datasets

### 5. Common Pitfalls to Avoid
- Mismatched vector dimensions
- Unnormalized vectors with IP/Cosine
- Insufficient memory for large indices
- Poor choice of index type
- Not considering search speed vs. accuracy trade-offs
- Forgetting to reshape query vectors
- Not handling API rate limits properly
- Ignoring memory constraints with large datasets

### 6. Ollama Implementation Learnings
- **Model Management**:
  - Local LLM models can be run using Ollama
  - Models are downloaded and cached locally
  - Different models available (e.g., llama2, mistral)
  - Models can be pulled and run with simple commands

- **Basic Usage**:
  ```bash
  # Pull a model
  ollama pull llama2
  
  # Run a model
  ollama run llama2 "Your prompt here"
  ```

- **API Integration**:
  - Ollama provides a REST API
  - Can be integrated with Python applications
  - Supports streaming responses
  - Can be used as an alternative to cloud-based LLMs

- **Advantages**:
  - Runs locally, no internet required
  - No API rate limits
  - Complete control over model and data
  - Can work offline
  - Privacy-preserving (data stays local)

- **Limitations**:
  - Requires significant local compute resources
  - Model sizes can be large (several GB)
  - May be slower than cloud-based solutions
  - Limited to available local models

- **Best Practices**:
  - Choose appropriate model size for your hardware
  - Monitor system resources during operation
  - Consider using smaller models for testing
  - Implement proper error handling for local execution
  - Cache frequently used responses when possible

- **Use Cases**:
  - Development and testing without API keys
  - Privacy-sensitive applications
  - Offline applications
  - Custom model fine-tuning
  - Educational purposes

- **Integration with FAISS**:
  - Can generate embeddings locally using Ollama
  - Useful for privacy-sensitive vector search
  - Can be combined with FAISS for local semantic search
  - Enables complete offline search solutions

### 7. Advanced FAISS Implementation Learnings
- **Document Processing**:
  - Text chunking is crucial for large documents
  - Overlapping chunks (10 words) help maintain context
  - Chunk size (40 words) balances context and processing
  - Metadata tracking is essential for result interpretation

- **Error Handling and Robustness**:
  ```python
  # Example of robust error handling
  try:
      result = client.models.embed_content(...)
  except Exception as e:
      if attempt == max_retries - 1:
          print(f"❌ Failed after {max_retries} attempts: {e}")
          raise
      print(f"⚠️ Attempt {attempt + 1} failed: {str(e)}")
      time.sleep(5 * (attempt + 1))
  ```
  - Implement exponential backoff for API calls
  - Add retry logic for transient failures
  - Use proper error messages with visual indicators
  - Handle partial processing gracefully

- **Progress Tracking**:
  - Use clear visual indicators (emojis, separators)
  - Show progress for long-running operations
  - Display meaningful status messages
  - Track processing of individual chunks

- **API Rate Management**:
  - Add delays between API calls (1 second)
  - Implement exponential backoff
  - Monitor API response times
  - Handle quota limits gracefully

- **Search Results Presentation**:
  ```python
  print(f"\n#{rank + 1}: From {data['doc_name']} [{data['chunk_id']}]")
  print(f"Distance: {D[0][rank]:.4f}")
  print(f"Content: {data['chunk']}")
  ```
  - Show document source and chunk ID
  - Display similarity scores
  - Format results for readability
  - Include relevant metadata

- **Code Organization**:
  - Separate configuration constants
  - Use descriptive variable names
  - Add comprehensive docstrings
  - Include type hints
  - Group related functionality

- **Performance Considerations**:
  - Process documents sequentially
  - Implement proper error recovery
  - Monitor memory usage
  - Consider batch processing for large datasets

- **Best Practices from Implementation**:
  1. Always validate input data
  2. Implement proper error handling
  3. Add progress tracking
  4. Use clear visual feedback
  5. Document code thoroughly
  6. Handle API limits properly
  7. Maintain metadata with vectors
  8. Format output for readability

- **Common Implementation Challenges**:
  - API rate limiting
  - Memory management with large datasets
  - Error recovery during processing
  - Maintaining context across chunks
  - Balancing chunk size and overlap

### 8. Package Installation and Dependencies
- **Required Packages**:
  ```bash
  # Install Google Generative AI
  pip install google-generativeai
  
  # Install other dependencies
  pip install faiss-cpu numpy python-dotenv
  ```

- **Import Statements**:
  ```python
  # Correct import for Google Generative AI
  import google.generativeai as genai
  
  # Other imports
  import faiss
  import numpy as np
  from dotenv import load_dotenv
  ```

- **Common Installation Issues**:
  1. **ImportError: cannot import name 'genai'**:
     - Solution: Install google-generativeai package
     - Command: `pip install google-generativeai`
  
  2. **FAISS Installation Issues**:
     - For CPU: `pip install faiss-cpu`
     - For GPU: `pip install faiss-gpu`
     - Note: Choose appropriate version based on your system

  3. **Environment Variables**:
     - Create `.env` file in project root
     - Add: `GEMINI_API_KEY=your_api_key_here`
     - Ensure dotenv is installed: `pip install python-dotenv`

- **Version Compatibility**:
  - Check package versions in requirements.txt
  - Update packages regularly
  - Test with different Python versions

- **Troubleshooting Steps**:
  1. Verify package installation:
     ```bash
     pip list | grep -E "google-generativeai|faiss|numpy|python-dotenv"
     ```
  
  2. Check Python environment:
     ```bash
     python -c "import google.generativeai as genai; print(genai.__version__)"
     ```
  
  3. Verify API key:
     ```python
     import os
     from dotenv import load_dotenv
     load_dotenv()
     print("API Key present:", bool(os.getenv("GEMINI_API_KEY")))
     ```

- **Gemini Client Initialization**:
  ```python
  # Correct way to initialize Gemini client
  import google.generativeai as genai
  genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
  
  # Using the client
  result = genai.models.embed_content(...)
  ```

- **Common Initialization Errors**:
  1. **AttributeError: module 'google.generativeai' has no attribute 'Client'**:
     - Solution: Use `genai.configure()` instead of `genai.Client()`
     - The library uses a configuration-based approach
  
  2. **API Key Issues**:
     - Ensure API key is properly set in .env file
     - Verify key format and permissions
     - Check for any special characters in the key
  
- **Embedding Generation with Gemini**:
  ```python
  # Correct way to generate embeddings
  result = genai.embed_content(
      model="models/embedding-001",
      content=text,
      task_type="RETRIEVAL_DOCUMENT"
  )
  embedding = np.array(result['embedding'], dtype=np.float32)
  ```

- **Common Embedding Errors**:
  1. **AttributeError: module 'google.generativeai' has no attribute 'models'**:
     - Solution: Use `genai.embed_content()` directly
     - The embedding API is accessed through the main module
  
  2. **Model Selection**:
     - Use `models/embedding-001` for embeddings
     - Different models available for different tasks
     - Check model availability in your region

  3. **Response Format**:
     - Embeddings are returned in the 'embedding' key
     - Convert to numpy array for FAISS
     - Ensure proper dtype (float32)
  
### 9. Quota Management Strategies
- **Global Quota Tracking**:
  ```python
  # Global variables for quota management
  QUOTA_RESET_TIME = None
  QUOTA_EXHAUSTED = False
  MIN_WAIT_TIME = 60  # Minimum wait time in seconds
  ```

- **Quota Status Checking**:
  ```python
  def check_quota_status() -> bool:
      if not QUOTA_EXHAUSTED:
          return True
      if QUOTA_RESET_TIME and datetime.now() < QUOTA_RESET_TIME:
          wait_seconds = (QUOTA_RESET_TIME - datetime.now()).total_seconds()
          time.sleep(wait_seconds)
          QUOTA_EXHAUSTED = False
          QUOTA_RESET_TIME = None
          return True
      return False
  ```

- **Error Handling for Quota Exhaustion**:
  ```python
  if "quota" in str(e).lower() or "429" in str(e):
      QUOTA_EXHAUSTED = True
      QUOTA_RESET_TIME = datetime.now() + timedelta(minutes=1)
      time.sleep(MIN_WAIT_TIME)
      continue
  ```

- **Best Practices for Quota Management**:
  1. Implement global quota tracking
  2. Use appropriate wait times
  3. Add exponential backoff
  4. Monitor quota usage
  5. Handle partial processing
  6. Provide clear user feedback
  7. Implement proper retry logic
  8. Consider batch processing

- **Common Quota-Related Issues**:
  1. **429 Resource Exhausted**:
     - Solution: Implement proper wait times
     - Use exponential backoff
     - Track reset periods
  
  2. **Partial Processing**:
     - Solution: Save progress
     - Implement checkpointing
     - Allow resumption
  
  3. **Rate Limiting**:
     - Solution: Add delays between calls
     - Use batch processing
     - Monitor API responses
  
### 10. Text Chunking Strategies
- **Why Overlap is Important**:
  ```python
  # Current implementation with overlap
  CHUNK_SIZE = 40  # Number of words per chunk
  CHUNK_OVERLAP = 10  # Number of words to overlap between chunks
  ```
  1. **Context Preservation**:
     - Prevents loss of context at chunk boundaries
     - Maintains semantic coherence
     - Helps in understanding relationships between chunks

  2. **Search Quality**:
     - Improves search result relevance
     - Reduces edge-case misses
     - Better handling of queries spanning chunk boundaries

  3. **Example Without Overlap**:
     ```python
     # Without overlap
     text = "The quick brown fox jumps over the lazy dog. The dog was sleeping peacefully."
     chunks = [
         "The quick brown fox jumps over the lazy dog.",
         "The dog was sleeping peacefully."
     ]
     # Query "Why was the dog sleeping?" might miss context
     ```

  4. **Example With Overlap**:
     ```python
     # With overlap
     text = "The quick brown fox jumps over the lazy dog. The dog was sleeping peacefully."
     chunks = [
         "The quick brown fox jumps over the lazy dog.",
         "the lazy dog. The dog was sleeping peacefully."
     ]
     # Query "Why was the dog sleeping?" captures full context
     ```

- **Alternative Chunking Strategies**:
  1. **Sentence-Based Chunking**:
     ```python
     def chunk_by_sentences(text: str) -> list:
         import nltk
         nltk.download('punkt')
         sentences = nltk.sent_tokenize(text)
         return sentences
     ```
     - Pros: Natural language boundaries
     - Cons: Variable chunk sizes

  2. **Paragraph-Based Chunking**:
     ```python
     def chunk_by_paragraphs(text: str) -> list:
         paragraphs = text.split('\n\n')
         return [p.strip() for p in paragraphs if p.strip()]
     ```
     - Pros: Semantic coherence
     - Cons: May be too large for some models

  3. **Sliding Window**:
     ```python
     def sliding_window(text: str, window_size: int, step_size: int) -> list:
         words = text.split()
         return [' '.join(words[i:i+window_size]) 
                for i in range(0, len(words), step_size)]
     ```
     - Pros: Consistent size, controlled overlap
     - Cons: May split sentences

  4. **Content-Aware Chunking**:
     ```python
     def content_aware_chunking(text: str, max_size: int) -> list:
         # Split at natural boundaries (headers, lists, etc.)
         # while respecting max_size
         pass
     ```
     - Pros: Respects document structure
     - Cons: More complex implementation

- **Choosing the Right Strategy**:
  1. **Consider Your Use Case**:
     - Search vs. classification
     - Document type (structured vs. unstructured)
     - Query patterns

  2. **Model Limitations**:
     - Maximum context length
     - Token limits
     - Processing capabilities

  3. **Performance Considerations**:
     - Number of chunks
     - Overlap overhead
     - Processing time

  4. **Quality Metrics**:
     - Search relevance
     - Context preservation
     - Query coverage

- **Best Practices**:
  1. Start with simple word-based chunking
  2. Add overlap for better context
  3. Monitor search quality
  4. Adjust chunk size based on content
  5. Consider document structure
  6. Test with real queries
  7. Balance chunk size and overlap
  8. Document your chunking strategy
  
### 11. Progress Tracking and Quota Management
- **Progress Saving and Loading**:
  ```python
  # Progress tracking files
  PROGRESS_FILE = "faiss_progress.pkl"  # For embeddings
  METADATA_FILE = "faiss_metadata.json"  # For document metadata

  def save_progress(chunks, metadata):
      """Save current progress to disk"""
      try:
          with open(PROGRESS_FILE, 'wb') as f:
              pickle.dump(chunks, f)
          with open(METADATA_FILE, 'w') as f:
              json.dump(metadata, f)
          print("💾 Progress saved successfully")
      except Exception as e:
          print(f"⚠️ Could not save progress: {e}")
  ```
  - Saves embeddings using pickle
  - Saves metadata using JSON
  - Handles errors gracefully
  - Provides clear feedback

- **Progress Loading**:
  ```python
  def load_progress():
      """Load progress from disk if available"""
      try:
          if os.path.exists(PROGRESS_FILE) and os.path.exists(METADATA_FILE):
              with open(PROGRESS_FILE, 'rb') as f:
                  chunks = pickle.load(f)
              with open(METADATA_FILE, 'r') as f:
                  metadata = json.load(f)
              print(f"📂 Loaded {len(chunks)} previously processed chunks")
              return chunks, metadata
      except Exception as e:
          print(f"⚠️ Could not load progress: {e}")
      return [], []
  ```
  - Checks for existing progress files
  - Loads both embeddings and metadata
  - Reports number of loaded chunks
  - Returns empty lists if no progress exists

- **Quota Management**:
  ```python
  # Quota management variables
  QUOTA_RESET_TIME = None
  QUOTA_EXHAUSTED = False
  MIN_WAIT_TIME = 60  # Minimum wait time in seconds
  MAX_WAIT_TIME = 300  # Maximum wait time in seconds
  current_wait_time = MIN_WAIT_TIME

  def check_quota_status() -> bool:
      """Check if we should wait due to quota exhaustion"""
      global QUOTA_RESET_TIME, QUOTA_EXHAUSTED, current_wait_time
      
      if not QUOTA_EXHAUSTED:
          return True
          
      if QUOTA_RESET_TIME and datetime.now() < QUOTA_RESET_TIME:
          wait_seconds = (QUOTA_RESET_TIME - datetime.now()).total_seconds()
          print(f"⏳ Quota exhausted. Waiting {wait_seconds:.0f} seconds until reset...")
          time.sleep(wait_seconds)
          QUOTA_EXHAUSTED = False
          QUOTA_RESET_TIME = None
          current_wait_time = MIN_WAIT_TIME
          return True
          
      return False
  ```
  - Tracks quota exhaustion status
  - Implements exponential backoff
  - Provides clear wait time feedback
  - Resets wait time on success

- **Best Practices for Progress Tracking**:
  1. Save progress after each file
  2. Save progress on errors
  3. Use appropriate file formats
  4. Provide clear feedback
  5. Handle errors gracefully
  6. Track processed files
  7. Skip already processed content
  8. Maintain metadata integrity

- **Best Practices for Quota Management**:
  1. Implement exponential backoff
  2. Set reasonable wait time limits
  3. Provide clear status messages
  4. Track quota reset times
  5. Handle partial processing
  6. Save progress before waiting
  7. Reset wait times on success
  8. Monitor API responses

- **Common Progress Tracking Issues**:
  1. **File Corruption**:
     - Solution: Use separate files for embeddings and metadata
     - Implement error handling
     - Validate loaded data
  
  2. **Memory Issues**:
     - Solution: Process files sequentially
     - Save progress frequently
     - Clear memory when possible
  
  3. **Partial Processing**:
     - Solution: Track processed files
     - Skip completed content
     - Maintain metadata integrity

- **Common Quota Management Issues**:
  1. **429 Resource Exhausted**:
     - Solution: Implement proper wait times
     - Use exponential backoff
     - Track reset periods
  
  2. **Inconsistent Wait Times**:
     - Solution: Use global wait time tracking
     - Implement proper backoff
     - Reset on success
  
  3. **Progress Loss**:
     - Solution: Save before waiting
     - Handle errors gracefully
     - Maintain metadata
  
### 12. Code Flow Explanation with Print Statements

#### 1. Initial Setup and Configuration
```python
# Load environment variables
load_dotenv()
print("🔧 Loading environment variables...")

# Quota management variables
QUOTA_RESET_TIME = None
QUOTA_EXHAUSTED = False
MIN_WAIT_TIME = 60  # Minimum wait time in seconds
MAX_WAIT_TIME = 300  # Maximum wait time in seconds
current_wait_time = MIN_WAIT_TIME
print("⚙️ Initializing quota management system...")

# Progress tracking files
PROGRESS_FILE = "faiss_progress.pkl"
METADATA_FILE = "faiss_metadata.json"
print(f"📁 Using progress files: {PROGRESS_FILE}, {METADATA_FILE}")
```

#### 2. Progress Loading
```python
print("\n📂 Attempting to load previous progress...")
all_chunks, metadata = load_progress()
processed_files = {item['doc_name'] for item in metadata}
print(f"✅ Loaded {len(all_chunks)} previously processed chunks")
print(f"📋 Found {len(processed_files)} processed files")
```

#### 3. Document Processing Loop
```python
print(f"\n📂 Processing documents from {DOC_PATH}")
print("=" * 50)

for file in DOC_PATH.glob("*.txt"):
    if file.name in processed_files:
        print(f"⏩ Skipping already processed file: {file.name}")
        continue
        
    print(f"\n📄 Processing {file.name}")
    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
            chunks = chunk_text(content)
            print(f"  → Split into {len(chunks)} chunks")
            
            for idx, chunk in enumerate(chunks):
                print(f"  → Getting embedding for chunk {idx + 1}/{len(chunks)}")
                embedding = get_embedding(chunk)
                all_chunks.append(embedding)
                metadata.append({
                    "doc_name": file.name,
                    "chunk": chunk,
                    "chunk_id": f"{file.stem}_{idx}"
                })
                time.sleep(1)  # Small delay between API calls
            
            processed_files.add(file.name)
            print(f"✅ Successfully processed {file.name}")
            save_progress(all_chunks, metadata)
            
    except Exception as e:
        print(f"❌ Error processing {file.name}: {e}")
        save_progress(all_chunks, metadata)
        continue
```

#### 4. FAISS Index Creation
```python
print("\n🔨 Creating FAISS index")
print("=" * 50)

try:
    dimension = len(all_chunks[0])
    print(f"📏 Vector dimension: {dimension}")
    index = faiss.IndexFlatL2(dimension)
    index.add(np.stack(all_chunks))
    print(f"✅ Index created successfully with {len(all_chunks)} vectors")
except Exception as e:
    print(f"❌ Error creating FAISS index: {e}")
    raise
```

#### 5. Example Search
```python
print("\n🔍 Running example search")
print("=" * 50)

query = "When will Dhoni retire?"
print(f"Query: {query}")

try:
    query_vec = get_embedding(query).reshape(1, -1)
    print("🔍 Searching index...")
    D, I = index.search(query_vec, k=3)
    
    print("\n📚 Top Matches:")
    for rank, idx in enumerate(I[0]):
        data = metadata[idx]
        print(f"\n#{rank + 1}: From {data['doc_name']} [{data['chunk_id']}]")
        print(f"Distance: {D[0][rank]:.4f}")
        print(f"Content: {data['chunk']}")
except Exception as e:
    print(f"❌ Error during search: {e}")
    raise
```

#### Expected Output Flow:
```
🔧 Loading environment variables...
⚙️ Initializing quota management system...
📁 Using progress files: faiss_progress.pkl, faiss_metadata.json

📂 Attempting to load previous progress...
✅ Loaded 0 previously processed chunks
📋 Found 0 processed files

📂 Processing documents from documents
==================================================

📄 Processing cricket.txt
  → Split into 5 chunks
  → Getting embedding for chunk 1/5
  → Getting embedding for chunk 2/5
  → Getting embedding for chunk 3/5
  → Getting embedding for chunk 4/5
  → Getting embedding for chunk 5/5
✅ Successfully processed cricket.txt
💾 Progress saved successfully

📄 Processing philosophy.txt
  → Split into 3 chunks
  → Getting embedding for chunk 1/3
  → Getting embedding for chunk 2/3
  → Getting embedding for chunk 3/3
✅ Successfully processed philosophy.txt
💾 Progress saved successfully

🔨 Creating FAISS index
==================================================
📏 Vector dimension: 768
✅ Index created successfully with 8 vectors

🔍 Running example search
==================================================
Query: When will Dhoni retire?
🔍 Searching index...

📚 Top Matches:

#1: From cricket.txt [cricket_2]
Distance: 0.1234
Content: [Relevant cricket content about Dhoni]

#2: From cricket.txt [cricket_1]
Distance: 0.2345
Content: [Another relevant cricket content]

#3: From cricket.txt [cricket_3]
Distance: 0.3456
Content: [Third relevant cricket content]
```

#### Key Points in the Flow:
1. **Initialization**:
   - Loads environment variables
   - Sets up quota management
   - Initializes progress tracking

2. **Progress Loading**:
   - Attempts to load previous progress
   - Creates set of processed files
   - Reports loaded chunks and files

3. **Document Processing**:
   - Processes each .txt file
   - Splits into chunks
   - Generates embeddings
   - Saves progress after each file

4. **FAISS Index Creation**:
   - Creates index with correct dimension
   - Adds all vectors to index
   - Reports success/failure

5. **Search Execution**:
   - Processes query
   - Searches index
   - Displays results with metadata

6. **Error Handling**:
   - Saves progress on errors
   - Provides clear error messages
   - Continues processing other files

7. **Progress Tracking**:
   - Saves after each file
   - Saves on errors
   - Provides clear feedback

8. **Quota Management**:
   - Implements delays between API calls
   - Handles quota exhaustion
   - Provides wait time feedback
  