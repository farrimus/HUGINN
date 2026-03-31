// src/components/BoardPanel.tsx
//
// Tribe post board rendered inline in the terminal.
// Posts display in chronological order (oldest first).
// Own posts have [Delete] → confirm flow before DELETE fires.

import { TribePost } from '../types/terminal';

interface BoardPanelProps {
  posts: TribePost[];
  walletAddress: string | null;
  tribeId: number;
  confirmDeleteId: string | null;
  showPostForm: boolean;
  postDraft: string;
  apiBaseUrl: string;
  onUpdate: (patch: {
    boardPosts?: TribePost[];
    boardConfirmDeleteId?: string | null;
    boardShowPostForm?: boolean;
    boardPostDraft?: string;
  }) => void;
}

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function formatPostDate(isoStr: string): string {
  try {
    const d = new Date(isoStr);
    const mon = MONTHS[d.getUTCMonth()];
    const day = String(d.getUTCDate()).padStart(2, '0');
    const hh = String(d.getUTCHours()).padStart(2, '0');
    const mm = String(d.getUTCMinutes()).padStart(2, '0');
    return `${mon} ${day} ${hh}:${mm}`;
  } catch {
    return isoStr.slice(0, 16);
  }
}

export function BoardPanel({
  posts,
  walletAddress,
  tribeId,
  confirmDeleteId,
  showPostForm,
  postDraft,
  apiBaseUrl,
  onUpdate,
}: BoardPanelProps) {

  const handleDelete = async (postId: string) => {
    if (!walletAddress) return;
    try {
      const res = await fetch(`${apiBaseUrl}/tribe-posts/${tribeId}/${postId}`, {
        method: 'DELETE',
        headers: { 'X-Wallet-Address': walletAddress },
      });
      if (!res.ok) {
        console.error('tribe board: delete failed', res.status);
        return;
      }
      onUpdate({ boardConfirmDeleteId: null });
      // SSE will remove the post from the list
    } catch (err) {
      console.error('tribe board: delete error', err);
    }
  };

  const handlePost = async () => {
    if (!walletAddress || !postDraft.trim()) return;
    try {
      const res = await fetch(`${apiBaseUrl}/tribe-posts/${tribeId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Wallet-Address': walletAddress,
        },
        body: JSON.stringify({ message: postDraft.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        console.error('tribe board: post failed', (err as { detail?: string }).detail || res.status);
        return;
      }
      onUpdate({ boardShowPostForm: false, boardPostDraft: '' });
      // SSE will add the new post
    } catch (err) {
      console.error('tribe board: post error', err);
    }
  };

  return (
    <div className="board-panel">
      <div className="board-header">
        TRIBE BOARD &mdash; {posts.length} post{posts.length !== 1 ? 's' : ''}
      </div>
      <div className="board-divider" />

      {posts.length === 0 && (
        <div className="board-empty">No posts yet.</div>
      )}

      {posts.map(post => (
        <div key={post.id} className="board-post">
          <div className="board-post-header">
            <span className="board-post-name">{post.poster_name}</span>
            <span className="board-post-date">&nbsp;&nbsp;[{formatPostDate(post.created_at)}]</span>
          </div>
          <div className="board-post-message">{post.message}</div>
          {walletAddress && post.poster_wallet === walletAddress && (
            <div className="board-post-actions">
              {confirmDeleteId === post.id ? (
                <>
                  <span
                    className="terminal-cmd-link board-delete-confirm"
                    onClick={() => handleDelete(post.id)}
                  >
                    [Confirm Delete]
                  </span>
                  {' '}
                  <span
                    className="terminal-cmd-link"
                    onClick={() => onUpdate({ boardConfirmDeleteId: null })}
                  >
                    [Cancel]
                  </span>
                </>
              ) : (
                <span
                  className="terminal-cmd-link board-delete"
                  onClick={() => onUpdate({ boardConfirmDeleteId: post.id })}
                >
                  [Delete]
                </span>
              )}
            </div>
          )}
        </div>
      ))}

      <div className="board-divider" />

      {showPostForm ? (
        <div className="board-post-form">
          <textarea
            className="board-textarea"
            value={postDraft}
            onChange={e => onUpdate({ boardPostDraft: e.target.value })}
            maxLength={280}
            rows={3}
            placeholder="Write your message..."
            autoFocus
          />
          <div className="board-char-count">{postDraft.length}/280</div>
          <div className="board-form-actions">
            <span className="terminal-cmd-link" onClick={handlePost}>
              [Submit]
            </span>
            {' '}
            <span
              className="terminal-cmd-link"
              onClick={() => onUpdate({ boardShowPostForm: false, boardPostDraft: '' })}
            >
              [Cancel]
            </span>
          </div>
        </div>
      ) : (
        <div className="board-actions">
          <span
            className="terminal-cmd-link"
            onClick={() => onUpdate({ boardShowPostForm: true, boardPostDraft: '' })}
          >
            [Post to Board]
          </span>
        </div>
      )}
    </div>
  );
}
