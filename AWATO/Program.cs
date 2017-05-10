using System;
using System.Collections.Generic;

namespace AWATO
{
    class Program
    {
        //Setup some globals to use for the story
        public static string glob_Name = null;
        public static bool glob_Intro = false;
        public static bool glob_DayOne = false;
        public static int glob_DayTime = 0;

        //Globals to allocate ingame assets
        public static int glob_Money = 1000;
        public static int glob_Employees = 1;
        public static int glob_Dep_Tickets = 1;
        public static int glob_Dep_Servers = 1;
        public static int glob_Dep_Bugs = 0;
        public static string glob_Commands = "Commands: '1' to check department status | '2' to assign orders to your employees | '3' to talk to the CIO | '4' to show the current time | '0' to show your stats | '9' to exit the game";
        //"Type '1' to check the status of your departments. \nType '2' to assign orders to your employees. \nType '3' to talk to the CIO. \nType '4' to show the current time.\nType '0' to show your stats.\nType '9' to exit the game.\n";

        //List with answers posible while getting the name at the start
        public static List<string> yes = new List<string>() { "yes", "y", "ye", "ok", "" };
        public static List<string> no = new List<string>() { "no", "n" };
        public static List<string> AvailComm = new List<string>() { "1", "2", "3", "4", "0", "9" };

        //Tickets
        public static List<int> tick_NotHandled = new List<int>() { 5 };  //Start with ticket 5 because it's my favorite so far
        //Tickets that need to be dealt with 
        public static List<string> Tickets = new List<string>() { "My computer is haunted! Please send an exorsist!", "My computer keeps shouting puns at me, please fix it!", "My mouse ate my lunch! Can you send another?", "I unplugged all the cables and now the computer doesn't work, please help!", "Is my computer supposed to be on fire? Please help ASAP, it's getting too hot to work.", "It's not working! I've tried nothing and I'm all out of ideas!" };
        //Sollutions to open tickets
        public static List<string> tick_Sollutions = new List<string>() { "You tell the user to 'Try and turn it off and on again'. You assume this worked and close the ticket.", "You tell the user to check if all the cables are plugged in and close the ticket.", "You type up some random technobable and close the ticket.", "You tell the user to delete system32 and then get back to you. After that you close the ticket.", "You tell the user that they should've followed the office protocol, and close the ticket." };

        public static void Main(string[] args)
        {
            //Start game, introduction and getting the name
            Console.WriteLine("Welcome to A Week At The Office!");

            //Now get the name
            while(GetName() == false)
            {//Keep on looping
                Console.WriteLine("\nPlease state your name clearly, as to not interfere with office protocol.\n");
                GetName();
            }

            //Now that we have the name, let's continue.
            Console.WriteLine("Alright, " + glob_Name + ", welcome to your new job as IT manager!\n");

            //Now run the intro
            RunGlobIntro();

            //Start of day 1
            Console.WriteLine("Day 1: Monday");
            Console.WriteLine("Your funds: " + glob_Money);
            Console.WriteLine("Number of employees in your department (excluding you): " + glob_Employees);
            Console.WriteLine("The current time is 9:00 AM");

            //Run day 1
            DayOne();

            Console.ReadLine();
        }

        public static void DrawText(string Text)
        {//Draw text at the bottom of the screen
            int left = Console.CursorLeft;
            int top = Console.CursorTop;
            Console.SetCursorPosition(0, 25);
            Console.Write(Text);
            Console.SetCursorPosition(left, top);
        }

        public static void RemoveStaticText()
        {//Remove the text
            int left = Console.CursorLeft;
            int top = Console.CursorTop;
            Console.SetCursorPosition(0, 25);
            Console.Write(new string(' ', Console.WindowWidth));
            Console.SetCursorPosition(left, top);
        }

        public static int ProduceRandomNumber(int Min, int Max)
        {
            Random RandNum = new Random();
            return RandNum.Next(Min, Max);
        }

        public static bool CheckForCommand(string Command)
        {
            bool CheckCommand = false;
            foreach (string x in AvailComm)
            {
                if (Command == x)
                {
                    CheckCommand = true;
                }
            }

            return CheckCommand;
        }

        public static void AddHourToTime() => glob_DayTime++;

        public static bool GetName()
        {
            bool nameEntered = false;
            string raw_GetName = null;

            while (nameEntered == false)
            {
                Console.WriteLine("Before we begin, what is your name? \n");
                raw_GetName = Console.ReadLine();

                if (raw_GetName.Length <= 1)
                {//Make sure the name is at least 2 or more characters long
                    Console.WriteLine("Names that short are against office protocols! \n");
                }
                else if (raw_GetName.Length > 1)
                {//Name is long enough, continue
                    nameEntered = true;
                }
            }

            Console.WriteLine("Your name is " + raw_GetName + ", is this correct?");
            string raw_CorrectName = Console.ReadLine();

            bool AnswerInList = false;

            foreach (string a in yes)
            {
                if (raw_CorrectName.ToLower() == a)
                {//Answer found in the possible answers list
                    glob_Name = raw_GetName;    //Set the public to the name provided
                    AnswerInList = true;
                }
            }
            foreach(string b in no)
            {
                if (raw_CorrectName.ToLower() == b)
                {
                    return false;
                }
            }

            if (!AnswerInList)
            {
                Console.WriteLine("Please respond with 'yes' or 'no'.\n");
                return false;
            }

            return true;
        }

        public static void RunGlobIntro()
        {//Make sure the program runs, use a while loop.
            //Clear the console
            Console.Clear();
            while (glob_Intro == false)
            {   //Check if the user wishes to skip the intro or not
                Console.WriteLine("Do you wish to skip the intro? (type 1 for yes, 2 for no).\n");
                string skip_Intro = Console.ReadLine();

                if (skip_Intro == "1"){
                    glob_Intro = true;
                }
                else if (skip_Intro == "2")
                {
                    Console.WriteLine("\nDear Mr / Mrs, (cross out whatever doesn't apply to you)\n");
                    Console.WriteLine("Hello and welcome! You're the new IT manager here at GeneriCorp (inc), hired because of your 'interesting' credentials (you were also the only candidate, but that's beside the point).\n");
                    Console.WriteLine("In this new, 'exciting' job you'll be responsible for the entire IT department of GeneriCorp (inc), including the software, hardware, and, of course, the support center!\n");
                    Console.WriteLine("You start every day with a limited amount of time and resources. It's up to you to make sure that: \n");
                    Console.WriteLine("The servers stay operatonal.\n");
                    Console.WriteLine("The software used is 'bug free' (or something, just keep it working).\n");
                    Console.WriteLine("The phone lines are staffed, so that the employees of GeneriCorp (inc) can do their job properly. \n");
                    Console.WriteLine("For any additional questions, please contact the head of the IT department. Oh wait, that's you. I mean, for any additional questions, please refer to the documentation the last manager left, if any is available.\n");
                    Console.WriteLine("We here at GeneriCorp (inc) wish you the best of luck, and a lot of 'fun' here at your new place of employment! - Phus Roda, CIO of GeneriCorp (inc)\n");
                    Console.WriteLine("\nPress any key to continue.\n");
                    glob_Intro = true;
                    //Make sure the console stops so the user can read the intro
                    Console.ReadLine();
                }
                else
                {
                    Console.WriteLine("Sorry, but your answer isn't listed in any of the office protocols.");
                }
            }

            //Now clear the console
            Console.Clear();
        }

        public static void CheckDepartments()
        {//Check the departments
            bool RunDepartment = true;
            while (RunDepartment)
            {
                //Remove the old static text
                RemoveStaticText();

                //Create new text with info
                DrawText("Which department would you like to check? Type '1' to check open tickets, '2' to check your server(s) status and '3' to check the status of the IT department itself. " +
                    "Type '0' to return to the previous menu.");

                //Get the player action
                string PlayerAction = Console.ReadLine();

                if (PlayerAction == "1")
                {//Check the tickets
                    CheckTickets();
                }
                else if (PlayerAction == "2")
                {//Check the servers
                    CheckServers();
                }
                else if (PlayerAction == "3")
                {//Check the status of the IT department
                    CheckITDepartment();
                }
                else if (PlayerAction == "0")
                {//Return to the previous menu
                    RunDepartment = false;
                    return;
                }
                else
                {//Incorrect command
                    Console.WriteLine("You type " + PlayerAction + ", only to realise that that isn't one of the options.\n");
                }
            }
        }

        public static void CheckTickets()
        {//Check and handle tickets
            bool RunCheck = true;
            Console.Clear();

            //Remove the old text on screen
            RemoveStaticText();

            //Draw new text
            DrawText("You have " + glob_Dep_Tickets + (glob_Dep_Tickets >= 2 ? " open tickets" : " open ticket"));

            while (RunCheck)
            {
                int x = 0;
                if (glob_Dep_Tickets > 0)
                {
                    //Remove the bottom text
                    RemoveStaticText();

                    //Display the ticket info
                    Console.WriteLine("The open ticket reads: " + tick_NotHandled[x].ToString());

                    //Now write the new info
                    DrawText("What do you do? Type '1' to handle the ticket or '2' to ignore the tickets and go back to your desk.");

                    //Get the response from the user
                    string PlayerChoice =  Console.ReadLine();

                    if (PlayerChoice == "1")
                    {//Remove one ticket, add an hour to the timer as the ticket has been 'handled'
                        tick_NotHandled.RemoveAt(x);
                        x++;    //Increase the loop counter by one.
                        //Respond with a random 'sollution' by first creating a random number
                        int RandNr = ProduceRandomNumber(0, 4);
                        Console.WriteLine(tick_Sollutions[RandNr]); //Display the number
                        AddHourToTime();    //Add an hour to the counter
                        glob_Dep_Tickets--; //Remove a ticket from the counter
                    }
                    else if (PlayerChoice == "2")
                    {//Return to the previous menu
                        RunCheck = false;
                    }
                    else
                    {
                        Console.WriteLine("You bash your fist on the keyboard, typing '" + PlayerChoice + "'. Too bad it doesn't seem to do anything.");
                    }
                }
                else
                {
                    Console.WriteLine("You think to yourself 'well, nothing to do here!' And return to your desk. \nPress any key to continue.");
                    Console.ReadLine();
                    RunCheck = false;
                }
            }
        }

        public static void CheckServers()
        {//Check the servers for errors

        }

        public static void CheckITDepartment()
        {

        }

        public static void AssignOrders()
        {//Assign order to the workers

        }

        public static void TalkToTheCIO()
        {//Talk to the CIO, allows purchasing of new items

        }

        public static void ShowTime()
        {//Shows the current time

        }

        public static void ShowStats()
        {//Displays the stats
            Console.Clear();
            Console.WriteLine("Your funds: " + glob_Money);
            Console.WriteLine("Number of employees in your department (excluding you): " + glob_Employees);
            Console.WriteLine("Number of servers available: " + glob_Dep_Servers);
        }

        public static void QuitGame()
        {//Quits the game

        }

        public static void DayOne()
        {//Handle day 1
            while(glob_DayOne == false)
            {//Keep looping until the day is done
                //First, check if it isn't 5 PM yet
                if (glob_DayTime >= 8)
                {
                    glob_DayOne = true;
                    return;
                }

                //Make sure the old text is removed
                RemoveStaticText();

                //Draw the possible commands on the screen
                DrawText(glob_Commands);

                //Get the player action
                string PlayerAction = Console.ReadLine();

                //Check if the command is available
                if (CheckForCommand(PlayerAction) == true)
                {
                    if (PlayerAction == "1")
                    {//Check the status of the departments
                        CheckDepartments();
                    }
                    else if (PlayerAction == "2")
                    {//Assign orders
                        AssignOrders();
                    }
                    else if (PlayerAction == "3")
                    {//Talk to the CIO (store)
                        TalkToTheCIO();
                    }
                    else if (PlayerAction == "4")
                    {//Display the current time
                        ShowTime();
                    }
                    else if (PlayerAction == "0")
                    {//Display the player stats
                        ShowStats();
                    }
                    else if (PlayerAction == "9")
                    {//Quit the game
                        QuitGame();
                    }
                }
                else
                {//Command is not available
                    Console.WriteLine("The action was not recognized, and upset the people in HR because you didn't follow correct office protocol :( \n");
                }
            }
        }
    }
}

/*
Console.WriteLine(glob_Money);
glob_Money += 100;
Console.WriteLine(glob_Money);
Console.ReadLine();
*/
