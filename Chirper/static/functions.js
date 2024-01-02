const ws = true;

const characters ='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
function generateString(length) {
    let result = ' ';
    const charactersLength = characters.length;
    for ( let i = 0; i < length; i++ ) {
        result += characters.charAt(Math.floor(Math.random() * charactersLength));
    }
    return result;
}

//Creating the HTML for each Post
function postHTML(postJSON) {
    //Create the container for the entire post
    const postDiv = document.createElement('div');
    postDiv.className = 'post-box';
    postDiv.id = 'post_' + postJSON._id;

    //Create and append the email display
    const emailDiv = document.createElement('div');
    emailDiv.innerHTML = `<strong>${postJSON.email}</strong>`;
    postDiv.appendChild(emailDiv);

    //Create and append the title display
    const titleDiv = document.createElement('div');
    titleDiv.innerHTML = `<strong>Title:</strong> ${postJSON.title}`;
    postDiv.appendChild(titleDiv);

    //Create and append the description display
    const descriptionDiv = document.createElement('div');
    descriptionDiv.innerHTML = `<strong>Description:</strong> ${postJSON.description}`;
    postDiv.appendChild(descriptionDiv);

    //Create and append the question type display
    const questionTypeDiv = document.createElement('div');
    questionTypeDiv.id = 'question_type_' + postJSON._id;
    questionTypeDiv.textContent = postJSON.question_type;
    postDiv.appendChild(questionTypeDiv);

    //Create and append the timer
    const timerDiv = document.createElement('div');
    timerDiv.id = 'timer_' + postJSON._id;
    timerDiv.className = 'timer';
    const timeLeftValue = isNaN(postJSON.timeLeft) ? 20 : postJSON.timeLeft;
    // Update the textContent of timerDiv
    timerDiv.textContent = `Time left: ${timeLeftValue === 0 ? "Time Is Up" : timeLeftValue + " seconds"}`;
    postDiv.appendChild(timerDiv);

    //Create and append the image if present
    if (postJSON.image_path) {
        const img = document.createElement('img');
        img.src = postJSON.image_path;
        img.alt = 'Image';
        img.style.maxWidth = '100%';
        img.style.display = 'block';
        img.style.marginBottom = '10px';
        postDiv.appendChild(img);
    }

    if (postJSON.timeLeft !== "0"){
        //Create and append the answer input or multiple-choice inputs
        if (postJSON.question_type === "Open Ended") {
            const answerInput = document.createElement('input');
            answerInput.type = 'text';
            answerInput.placeholder = 'Enter your answer';
            answerInput.id = 'open_answer_' + postJSON._id;
            postDiv.appendChild(answerInput);
        } 
        else {
            //Create and append multiple-choice options
            const choices = ['A', 'B', 'C', 'D'];
            choices.forEach((choice) => {
                const choiceLabel = document.createElement('label');
                const choiceInput = document.createElement('input');
                choiceInput.type = 'radio';
                choiceInput.name = 'choice_' + postJSON._id;
                choiceInput.value = choice;
                choiceLabel.appendChild(choiceInput);
                choiceLabel.appendChild(document.createTextNode(choice));
                postDiv.appendChild(choiceLabel);
                postDiv.appendChild(document.createElement('br'));
            });
        }
        //Create and append the submit button
        const submitButton = document.createElement('button');
        submitButton.textContent = 'Submit Answer';
        submitButton.onclick = function() { submitAnswer(postJSON._id); };
        postDiv.appendChild(submitButton);
    }

    return postDiv;
}

//Adding the postHTML on indexHTML
function addPostToPosts(postJSON) {
    var posts = document.getElementById("postHistory");
    posts.appendChild(postHTML(postJSON));
}

//Updates all Posts
function updatePosts() {
    const request = new XMLHttpRequest();
    request.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            clearPosts();
            const posts = JSON.parse(this.response);
            for (const post of posts) {
                addPostToPosts(post);
            }
        }
    }

    request.open("GET", "/post-history");
    request.send();
}

//Clearing Posts
function clearPosts() {
    const posts = document.getElementById("postHistory");
    posts.innerHTML = "";
}

//Constantly calls updatePosts() on startup
function welcome() {
    updatePosts();
}

//Function to update the timer for each post
function updateTimer(postID, timeLeft) {
    //timer_123 from <div id='timer_" + postID
    const timerData = document.getElementById('timer_' + postID);
    if (timerData) {
        if (timeLeft==="0"){
            timerData.textContent = 'Time Left: Time Is Up';
        }
        else {
            timerData.textContent = 'Time Left: ' + timeLeft + 's';
        }
    }
}