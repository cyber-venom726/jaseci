import from mtllm { Model }


glob llm = Model(model_name="gpt-4o");


node Weather {
    has temperature: float = 22.5,
        humidity: float = 60.0,
        windSpeed: float = 5.0;

    def check_weather(location: tuple(float, float), date: tuple(str, str)) {
        # Logic to check the weather conditions
        # This could involve querying a weather API or using predefined data
        self.temperature =
            22.5;
        # Example temperature in Celsius
        self.humidity =
            60.0;
        # Example humidity percentage
        self.windSpeed =
            5.0;
    # Example wind speed in km/h
     }

    can interact with WeatherWalker entry {
        print(
            f"Weather at location {location[0]}, {location[1]}: "f"Temperature: {self.temperature}°C, "f"Humidity: {self.humidity}%, "f"Wind Speed: {self.windSpeed} km/h"
        );
    }
}


sem Weather= "Weather reporting agent";


node GoogleMaps {
    has location: tuple(float, float) = (40.7128, -74.0060);

    def get_location(location: str) {
        # Logic to get the current location
        # This could involve using GPS or predefined data
        self.location =
            (40.7128, -74.0060);
    # Example location (latitude, longitude)
     }

    can interact with WeatherWalker entry {
        print(f"Location is {self.location[0]}, {self.location[1]}");
    }
}


enum Agent { WEATHER = "Weather" , GOOGLE_MAPS = "GoogleMaps" }


def AgentSelector(task: str, context: any, memory: dict) -> Agent byllm(
    method="Reason"
);


walker WeatherWalker {
    has query: str = input(
        "I am WeatherWalker. What would you like to know about the weather?"
    );

    can visit_next with `root entry {
        self.visit_by_llm(here, self);
    }
}


    def visit_by_llm(start_node: node, walker_obj: Walker) {
        # available_nodes = [node-->];
        where_next = AgentSelector(task=walker_obj.query, context=start_node, memory={});
        if where_next == Agent.WEATHER {
            visit [start_node->:Weather :->];
        } elif where_next == Agent.GOOGLE_MAPS {
            visit [start_node->:GoogleMaps :->];
        }
    }


with entry {
    n1 := Weather();
    n2 := GoogleMaps();
    root ++> n1;
    root ++> n2;
    n1 ++> n2;
    WeatherWalker() spawn root;
}
