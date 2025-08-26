import { GoogleGenAI, Type } from "@google/genai";
import React, { useState } from "react";
import { createRoot } from "react-dom/client";

const App = () => {
  type AppState = 'initial' | 'summarized' | 'generated';
  const [appState, setAppState] = useState<AppState>('initial');
  
  const [url, setUrl] = useState("");
  const [postSummary, setPostSummary] = useState("");
  const [commentsSummary, setCommentsSummary] = useState("");
  const [comments, setComments] = useState<string[]>([]);
  const [editedComments, setEditedComments] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [tone, setTone] = useState("Neutral");

  const tones = ["Neutral", "Informative", "Humorous", "Supportive"];

  const isValidRedditUrl = (url: string) => {
    // Regex to match a Reddit post URL, ensuring it has a post ID after /comments/
    const redditPostRegex = /^https?:\/\/(www\.)?reddit\.com\/r\/[a-zA-Z0-9_]+\/comments\/[a-zA-Z0-9]+/;
    return redditPostRegex.test(url);
  };
  
  const resetForNewUrl = () => {
    setPostSummary("");
    setCommentsSummary("");
    setComments([]);
    setEditedComments([]);
    setCopiedIndex(null);
    setError("");
    setAppState('initial');
  };

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUrl(e.target.value);
    if (appState !== 'initial') {
      resetForNewUrl();
    }
  };

  const handleAnalyze = async () => {
    if (!isValidRedditUrl(url)) {
      setError("Please enter a valid Reddit post URL (e.g., reddit.com/r/subreddit/comments/...).");
      return;
    }

    setLoading(true);
    // Reset previous results for the new analysis
    setError("");
    setPostSummary("");
    setCommentsSummary("");
    setComments([]);
    setEditedComments([]);
    setAppState('initial');


    try {
      const ai = new GoogleGenAI({ apiKey: process.env.API_KEY! });
      const prompt = `Based on the Reddit post at this URL: "${url}", your task is to provide a structured JSON response with two summaries:
      
1.  **postSummary**: Analyze the original post and summarize the key problem or question in plain language.
2.  **commentsSummary**: Scan the existing top comments (if any) and identify what’s already been said, so you don’t repeat it.
      
Your final output must be a single, valid JSON object with the keys "postSummary" and "commentsSummary".`;
      
      const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: prompt,
        config: {
          responseMimeType: "application/json",
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              postSummary: {
                type: Type.STRING,
                description: "A concise summary of the original post's key problem or question."
              },
              commentsSummary: {
                type: Type.STRING,
                description: "A summary of the sentiment and key points from the existing comments."
              }
            }
          }
        }
      });
      
      const responseJson = JSON.parse(response.text);
      setPostSummary(responseJson.postSummary);
      setCommentsSummary(responseJson.commentsSummary);
      setAppState('summarized');

    } catch (err) {
      console.error(err);
      setError("Failed to analyze the post. The URL may be invalid, private, or deleted. Please check and try again.");
      setAppState('initial'); // Reset state on failure so the user can try again
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateComments = async () => {
    setLoading(true);
    setError("");
    setCopiedIndex(null);
    
    try {
      const ai = new GoogleGenAI({ apiKey: process.env.API_KEY! });
      
      const existingCommentsPromptSection = comments.length > 0
        ? `You have already generated the following comments. DO NOT repeat them or provide similar suggestions:\n${comments.map(c => `- "${c}"`).join('\n')}\n`
        : '';

      const prompt = `Adopt the persona of a seasoned Reddit user who is a subject-matter expert on the topic of this post. You are a peer in the community, not a marketer. You have already analyzed a Reddit post and its comments.
      
Here is the summary of the post:
"${postSummary}"
      
Here is the summary of the existing comments:
"${commentsSummary}"
      
${existingCommentsPromptSection}
Now, your task is to generate a **brand new** array of 3 unique comment replies. Each of these comments must be written in natural, human-like language, and should follow the selected tone of "${tone}".

Here are the rules for your reply:
*"1. **Be Human:** Write like a real person. Use a conversational, peer-to-peer style. Use contractions (e.g., you're, it's, that's) and don't be overly formal. Your goal is to be helpful and relatable.
2. **Be Digestible:** Your comment must be easy to read. Use short sentences. Keep paragraphs to 2-3 sentences max. If you are explaining something complex or listing items, *strongly prefer* using bullet points for clarity. This is especially crucial for 'Informative' and 'Supportive' tones.
3. **Add Unique Value:** Add a perspective or best practice that hasn’t been covered—something actionable, practical, or a nuance most people overlook.
4. **Maintain Tone:** The tone must be conversational, concise, peer-to-peer, and strictly adhere to the selected tone: **${tone}**. Avoid jargon, sales pitches, or polished marketing speak.
5. **Anchor in Reality (If Applicable):** If relevant, anchor your point in real-world SaaS/finance best practices (e.g., retry timing, pre-dunning, churn prevention, automation, data hygiene).
6. **End Smart:** End with a thought-provoking note, not a call to action."*

Crucially, do not mention being an AI. Your response should be indistinguishable from a genuine, experienced Reddit user. Your final output must be a single, valid JSON object with the key "newComments", which contains an array of 3 comment strings.`;

      const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: prompt,
        config: {
          responseMimeType: "application/json",
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              newComments: {
                type: Type.ARRAY,
                description: "An array of 3 new, non-salesy comments to add to the discussion.",
                items: {
                  type: Type.STRING
                }
              }
            }
          }
        }
      });

      const responseJson = JSON.parse(response.text);
      setComments(prevComments => [...prevComments, ...responseJson.newComments]);
      setEditedComments(prevEditedComments => [...prevEditedComments, ...responseJson.newComments]);
      setAppState('generated');

    } catch (err) {
      console.error(err);
      setError("Failed to generate comments. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const handleCopy = (text: string, index: number) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };
  
  const handleCommentChange = (e: React.ChangeEvent<HTMLTextAreaElement>, index: number) => {
    const newEditedComments = [...editedComments];
    newEditedComments[index] = e.target.value;
    setEditedComments(newEditedComments);
  };

  return (
    <div className="container">
      <h1>Reddit Comment Generator</h1>
      <p>Enter a Reddit post link to get summaries and generate engaging comments.</p>
      
      <div className="input-group">
        <input
          type="url"
          className="url-input"
          placeholder="https://www.reddit.com/r/..."
          value={url}
          onChange={handleUrlChange}
          aria-label="Reddit URL"
          disabled={loading}
        />
      </div>

      {appState === 'initial' && (
        <button
          className="generate-button"
          onClick={handleAnalyze}
          disabled={loading || !url}
          aria-busy={loading}
        >
          {loading ? (
            <>
              <div className="spinner" role="status" aria-label="Loading"></div>
              <span>Analyzing...</span>
            </>
          ) : (
            "Analyze Post"
          )}
        </button>
      )}

      {error && <p className="error-message" role="alert">{error}</p>}

      {(appState === 'summarized' || appState === 'generated') && (
        <div className="results-container">
          {postSummary && (
            <div className="output-container" aria-live="polite">
              <div className="output-header">
                <h2>Post Summary</h2>
              </div>
              <p>{postSummary}</p>
            </div>
          )}

          {commentsSummary && (
            <div className="output-container" aria-live="polite">
              <div className="output-header">
                <h2>Comments Summary</h2>
              </div>
              <p>{commentsSummary}</p>
            </div>
          )}
        </div>
      )}

      {(appState === 'summarized' || (appState === 'generated' && loading)) && (
         <div className="action-step-container">
         <div className="tone-selector">
           <p className="tone-label">Select a tone for your comment:</p>
           <div className="tone-options">
               {tones.map((t) => (
               <div key={t}>
                   <input
                   type="radio"
                   id={`tone-${t}`}
                   name="tone"
                   value={t}
                   checked={tone === t}
                   onChange={() => setTone(t)}
                   disabled={loading}
                   />
                   <label htmlFor={`tone-${t}`}>{t}</label>
               </div>
               ))}
           </div>
         </div>
         <button
           className="generate-button"
           onClick={handleGenerateComments}
           disabled={loading}
           aria-busy={loading}
         >
           {loading ? (
             <>
               <div className="spinner" role="status" aria-label="Loading"></div>
               <span>Generating...</span>
             </>
           ) : (
             "Generate Comments"
           )}
         </button>
       </div>
      )}

      {appState === 'generated' && (
        <div className="results-container">
          <div className="output-container" aria-live="polite">
            <div className="output-header">
              <h2>Generated Comments</h2>
            </div>
            <div className="comment-list">
              {editedComments.map((comment, index) => (
                <div key={index} className="comment-item">
                  <textarea
                    className="editable-comment"
                    value={comment}
                    onChange={(e) => handleCommentChange(e, index)}
                    aria-label={`Editable comment ${index + 1}`}
                  />
                  <button className="copy-button" onClick={() => handleCopy(comment, index)}>
                    {copiedIndex === index ? "Copied!" : "Copy"}
                  </button>
                </div>
              ))}
            </div>
          </div>
          
           {/* Tone selector is shown again before generating more */}
           <div className="action-step-container">
              <div className="tone-selector">
                <p className="tone-label">Select a new tone or generate more:</p>
                <div className="tone-options">
                    {tones.map((t) => (
                    <div key={t}>
                        <input
                        type="radio"
                        id={`tone-more-${t}`}
                        name="tone-more"
                        value={t}
                        checked={tone === t}
                        onChange={() => setTone(t)}
                        disabled={loading}
                        />
                        <label htmlFor={`tone-more-${t}`}>{t}</label>
                    </div>
                    ))}
                </div>
              </div>
            </div>

          <button
            className="generate-button regenerate-button"
            onClick={handleGenerateComments}
            disabled={loading}
            aria-busy={loading}
          >
            {loading ? (
              <>
                <div className="spinner" role="status" aria-label="Loading"></div>
                <span>Generating More...</span>
              </>
            ) : (
              "Generate More"
            )}
          </button>
        </div>
      )}
    </div>
  );
};

const container = document.getElementById("root");
if (container) {
  const root = createRoot(container);
  root.render(<App />);
}
