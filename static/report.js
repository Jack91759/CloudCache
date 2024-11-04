document.getElementById('issueForm').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent form submission

    const issueDescription = document.getElementById('issueDescription').value;

    // Create a new issue item
    const issueItem = document.createElement('div');
    issueItem.className = 'issue-item';
    issueItem.innerHTML = `
        <p>${issueDescription}</p>
        <button class="mark-done">Mark as Done</button>
    `;

    // Add event listener to the "Mark as Done" button
    issueItem.querySelector('.mark-done').addEventListener('click', function() {
        issueItem.style.textDecoration = 'line-through';
        issueItem.querySelector('.mark-done').disabled = true;
    });

    // Append the new issue to the issues list
    document.getElementById('issuesList').appendChild(issueItem);

    // Clear the input field
    document.getElementById('issueDescription').value = '';
});
