/**
 * Build Pagefind search index from book claim data.
 *
 * Indexes claims from index/*.json files with custom URLs pointing to
 * specific claim anchors in the rendered book pages.
 */

import * as pagefind from 'pagefind';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const INDEX_DIR = path.join(PROJECT_ROOT, 'index');
const BLOG_CONTENT = path.join(PROJECT_ROOT, 'blog', 'content', 'books');
const OUTPUT_DIR = process.env.OUTPUT_DIR
    || (fs.existsSync(path.join(PROJECT_ROOT, 'blog', 'public'))
        ? path.join(PROJECT_ROOT, 'blog', 'public')
        : path.join(PROJECT_ROOT, 'public'));

/**
 * Build a mapping from index filenames to blog post slugs.
 * Reads the blog posts to extract their actual slugs from frontmatter.
 */
function buildSlugMapping() {
    const mapping = {};

    // Read all blog posts and extract their slugs
    const posts = fs.readdirSync(BLOG_CONTENT).filter(f => f.endsWith('.md'));

    for (const postFile of posts) {
        const content = fs.readFileSync(path.join(BLOG_CONTENT, postFile), 'utf8');

        // Extract slug from frontmatter
        const slugMatch = content.match(/^slug:\s*"?([^"\n]+)"?/m);
        const slug = slugMatch ? slugMatch[1].trim() : postFile.replace('.md', '');

        // Extract title to help with matching
        const titleMatch = content.match(/^title:\s*"?([^"\n]+)"?/m);
        const title = titleMatch ? titleMatch[1].replace(/^"|"$/g, '').trim() : '';

        // The key for mapping is based on how index files are named
        // Index files use the original book name (with spaces)
        // We need to match them to blog posts

        mapping[postFile.replace('.md', '')] = {
            slug,
            title,
            filename: postFile
        };
    }

    return mapping;
}

/**
 * Find the blog post slug for a given index file.
 */
function findBlogSlug(indexFilename, slugMapping, bookTitle) {
    // Try direct match by converting index filename to slug format
    const indexSlug = indexFilename.replace(/ /g, '-').toLowerCase();

    // Check each blog post for a match
    for (const [postSlug, data] of Object.entries(slugMapping)) {
        // Match by title
        if (data.title && bookTitle &&
            data.title.toLowerCase() === bookTitle.toLowerCase()) {
            return data.slug;
        }

        // Match by slug similarity
        if (postSlug.startsWith(indexSlug) || indexSlug.startsWith(postSlug)) {
            return data.slug;
        }

        // Match by normalized comparison
        const normalizedIndex = indexFilename.toLowerCase().replace(/[^a-z0-9]/g, '');
        const normalizedPost = postSlug.toLowerCase().replace(/[^a-z0-9]/g, '');
        if (normalizedPost.includes(normalizedIndex) || normalizedIndex.includes(normalizedPost)) {
            return data.slug;
        }
    }

    // Fallback: convert index filename to slug format
    console.warn(`  Warning: No exact match for "${indexFilename}", using fallback slug`);
    return indexFilename.replace(/ /g, '-').toLowerCase();
}

async function buildSearchIndex() {
    console.log('Building Pagefind search index...\n');

    // Create the index
    const { index } = await pagefind.createIndex();

    // Build slug mapping from blog posts
    const slugMapping = buildSlugMapping();
    console.log(`Found ${Object.keys(slugMapping).length} blog posts\n`);

    // Load concept registry for labels
    const conceptsPath = path.join(INDEX_DIR, '_concepts.json');
    let concepts = {};
    if (fs.existsSync(conceptsPath)) {
        const conceptsData = JSON.parse(fs.readFileSync(conceptsPath, 'utf8'));
        concepts = conceptsData.concepts || {};
    }

    // Process each book index
    const indexFiles = fs.readdirSync(INDEX_DIR).filter(f =>
        f.endsWith('.json') && !f.startsWith('_')
    );

    let totalClaims = 0;

    for (const file of indexFiles) {
        const bookData = JSON.parse(
            fs.readFileSync(path.join(INDEX_DIR, file), 'utf8')
        );

        const bookTitle = bookData.book?.title || file.replace('.json', '');
        const bookAuthor = bookData.book?.author || '';
        const indexName = file.replace('.json', '');

        // Find the correct blog post slug for this book
        const blogSlug = findBlogSlug(indexName, slugMapping, bookTitle);

        const claims = bookData.claims || [];
        console.log(`Indexing ${file}: ${claims.length} claims → /books/${blogSlug}/`);

        for (const claim of claims) {
            // Get concept labels for display
            const conceptLabels = (claim.concepts || [])
                .map(c => concepts[c]?.label || c.replace(/_/g, ' '))
                .slice(0, 5);  // Limit to 5 concepts

            await index.addCustomRecord({
                url: `/books/${blogSlug}/#${claim.id}`,
                content: claim.text,
                language: 'en',
                meta: {
                    title: truncate(claim.text, 100),
                    book: bookTitle,
                    author: bookAuthor,
                    chapter: claim.chapter || '',
                    concepts: conceptLabels.join(', ')
                },
                filters: {
                    book: [blogSlug],
                    concepts: claim.concepts || []
                }
            });
            totalClaims++;
        }
    }

    console.log(`\nTotal claims indexed: ${totalClaims}`);

    // Write the index files
    const outputPath = path.join(OUTPUT_DIR, 'pagefind');
    await index.writeFiles({ outputPath });

    console.log(`\nSearch index written to: ${outputPath}`);

    // Report index size
    const files = fs.readdirSync(outputPath);
    let totalSize = 0;
    for (const f of files) {
        const stat = fs.statSync(path.join(outputPath, f));
        totalSize += stat.size;
    }
    console.log(`Index size: ${(totalSize / 1024).toFixed(1)} KB`);
}

function truncate(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength - 3) + '...';
}

// Run
buildSearchIndex().catch(err => {
    console.error('Error building search index:', err);
    process.exit(1);
});
