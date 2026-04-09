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

function slugify(title) {
    return title
        .toLowerCase()
        .trim()
        .replace(/[^\w\s-]/g, '')
        .replace(/[\s_]+/g, '-');
}

/**
 * Build a mapping from index filenames to blog post slugs.
 * Reads the generated blog posts and enforces the canonical slug contract.
 */
function buildSlugMapping() {
    const mapping = new Map();

    const posts = fs.readdirSync(BLOG_CONTENT).filter(f => f.endsWith('.md'));

    for (const postFile of posts) {
        const content = fs.readFileSync(path.join(BLOG_CONTENT, postFile), 'utf8');
        const fileSlug = postFile.replace('.md', '');

        const slugMatch = content.match(/^slug:\s*"?([^"\n]+)"?/m);
        const slug = slugMatch ? slugMatch[1].trim() : fileSlug;

        if (slug !== fileSlug) {
            throw new Error(
                `Generated post slug mismatch for "${postFile}": `
                + `frontmatter slug "${slug}" does not match filename slug "${fileSlug}". `
                + 'Regenerate blog/content from the canonical note filename before building Pagefind.'
            );
        }

        const titleMatch = content.match(/^title:\s*"?([^"\n]+)"?/m);
        const title = titleMatch ? titleMatch[1].replace(/^"|"$/g, '').trim() : '';

        if (mapping.has(fileSlug)) {
            throw new Error(`Duplicate generated post slug detected: "${fileSlug}"`);
        }

        mapping.set(fileSlug, {
            slug,
            title,
            filename: postFile
        });
    }

    return mapping;
}

/**
 * Validate that every canonical index file has an exact generated post match.
 */
function findMissingMappings(indexFiles, slugMapping) {
    return indexFiles
        .map(file => file.replace('.json', ''))
        .filter(indexName => !slugMapping.has(slugify(indexName)))
        .map(indexName => ({
            indexName,
            expectedSlug: slugify(indexName)
        }));
}

function getBlogSlug(indexFilename, slugMapping) {
    const canonicalSlug = slugify(indexFilename);
    const post = slugMapping.get(canonicalSlug);
    if (!post) {
        throw new Error(
            `No generated blog post found for canonical index "${indexFilename}" `
            + `(expected slug "${canonicalSlug}").`
        );
    }
    return post.slug;
}

async function buildSearchIndex() {
    console.log('Building Pagefind search index...\n');

    // Create the index
    const { index } = await pagefind.createIndex();

    // Build slug mapping from blog posts
    const slugMapping = buildSlugMapping();
    console.log(`Found ${slugMapping.size} blog posts\n`);

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

    const missingMappings = findMissingMappings(indexFiles, slugMapping);
    if (missingMappings.length > 0) {
        const details = missingMappings
            .slice(0, 10)
            .map(({ indexName, expectedSlug }) =>
                `  - ${indexName} -> expected blog/content/books/${expectedSlug}.md`
            )
            .join('\n');
        const remainder = missingMappings.length > 10
            ? `\n  ... and ${missingMappings.length - 10} more`
            : '';
        throw new Error(
            'Canonical slug audit failed. Pagefind now requires exact note/index slug alignment.\n'
            + `${details}${remainder}\n`
            + 'Rename the canonical book so notes/, index/, vectors, and concepts agree before publishing.'
        );
    }

    let totalClaims = 0;

    for (const file of indexFiles) {
        const bookData = JSON.parse(
            fs.readFileSync(path.join(INDEX_DIR, file), 'utf8')
        );

        const bookTitle = bookData.book?.title || file.replace('.json', '');
        const bookAuthor = bookData.book?.author || '';
        const indexName = file.replace('.json', '');

        const blogSlug = getBlogSlug(indexName, slugMapping);

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
