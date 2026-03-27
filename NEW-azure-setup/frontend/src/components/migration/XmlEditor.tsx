import { useState, useCallback } from "react";
import Editor from "@monaco-editor/react";
import { ChevronDown, FileCode2, Copy, Check } from "lucide-react";

interface XmlEditorProps {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
}

const SAMPLE_XMLS: Record<string, string> = {
  "HTTP Listener + Logger": `<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="
        http://www.mulesoft.org/schema/mule/core
        http://www.mulesoft.org/schema/mule/core/current/mule.xsd
        http://www.mulesoft.org/schema/mule/http
        http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd">

  <http:listener-config name="HTTP_Listener_config">
    <http:listener-connection host="0.0.0.0" port="8081"/>
  </http:listener-config>

  <flow name="helloWorldFlow">
    <http:listener config-ref="HTTP_Listener_config" path="/api/hello"/>
    <logger level="INFO" message="Received request: #[attributes.queryParams.name]"/>
    <set-payload value='{"message": "Hello, #[attributes.queryParams.name default \\"World\\"]!"}'
                 mimeType="application/json"/>
  </flow>
</mule>`,

  "REST API with Database": `<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http"
      xmlns:db="http://www.mulesoft.org/schema/mule/db"
      xmlns:ee="http://www.mulesoft.org/schema/mule/ee/core"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="
        http://www.mulesoft.org/schema/mule/core
        http://www.mulesoft.org/schema/mule/core/current/mule.xsd
        http://www.mulesoft.org/schema/mule/http
        http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd
        http://www.mulesoft.org/schema/mule/db
        http://www.mulesoft.org/schema/mule/db/current/mule-db.xsd
        http://www.mulesoft.org/schema/mule/ee/core
        http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd">

  <http:listener-config name="HTTP_Listener_config">
    <http:listener-connection host="0.0.0.0" port="8081"/>
  </http:listener-config>

  <db:config name="Database_Config">
    <db:my-sql-connection host="localhost" port="3306"
                          user="root" password="password" database="mydb"/>
  </db:config>

  <flow name="getUsersFlow">
    <http:listener config-ref="HTTP_Listener_config" path="/api/users" allowedMethods="GET"/>
    <db:select config-ref="Database_Config">
      <db:sql>SELECT * FROM users</db:sql>
    </db:select>
    <ee:transform>
      <ee:message>
        <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload map {
  id: $.id,
  name: $.name,
  email: $.email
}]]></ee:set-payload>
      </ee:message>
    </ee:transform>
  </flow>

  <flow name="createUserFlow">
    <http:listener config-ref="HTTP_Listener_config" path="/api/users" allowedMethods="POST"/>
    <ee:transform>
      <ee:message>
        <ee:set-variable variableName="userData"><![CDATA[%dw 2.0
output application/java
---
payload]]></ee:set-variable>
      </ee:message>
    </ee:transform>
    <db:insert config-ref="Database_Config">
      <db:sql>INSERT INTO users (name, email) VALUES (:name, :email)</db:sql>
      <db:input-parameters><![CDATA[#[{name: vars.userData.name, email: vars.userData.email}]]]></db:input-parameters>
    </db:insert>
    <set-payload value='{"status": "created"}' mimeType="application/json"/>
  </flow>
</mule>`,

  "Error Handling Flow": `<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="
        http://www.mulesoft.org/schema/mule/core
        http://www.mulesoft.org/schema/mule/core/current/mule.xsd
        http://www.mulesoft.org/schema/mule/http
        http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd">

  <http:listener-config name="HTTP_Listener_config">
    <http:listener-connection host="0.0.0.0" port="8081"/>
  </http:listener-config>

  <flow name="mainFlow">
    <http:listener config-ref="HTTP_Listener_config" path="/api/process"/>
    <logger level="INFO" message="Processing request"/>
    <choice>
      <when expression="#[attributes.queryParams.type == 'A']">
        <flow-ref name="processTypeAFlow"/>
      </when>
      <when expression="#[attributes.queryParams.type == 'B']">
        <flow-ref name="processTypeBFlow"/>
      </when>
      <otherwise>
        <set-payload value='{"error": "Unknown type"}' mimeType="application/json"/>
      </otherwise>
    </choice>
    <error-handler>
      <on-error-propagate type="HTTP:NOT_FOUND">
        <set-payload value='{"error": "Resource not found"}' mimeType="application/json"/>
      </on-error-propagate>
      <on-error-continue type="ANY">
        <logger level="ERROR" message="Error: #[error.description]"/>
        <set-payload value='{"error": "Internal server error"}' mimeType="application/json"/>
      </on-error-continue>
    </error-handler>
  </flow>

  <sub-flow name="processTypeAFlow">
    <logger level="INFO" message="Processing Type A"/>
    <set-payload value='{"result": "Processed Type A"}' mimeType="application/json"/>
  </sub-flow>

  <sub-flow name="processTypeBFlow">
    <logger level="INFO" message="Processing Type B"/>
    <set-payload value='{"result": "Processed Type B"}' mimeType="application/json"/>
  </sub-flow>
</mule>`,

  "Multiple Flows (Users + Orders)": `<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http"
      xmlns:db="http://www.mulesoft.org/schema/mule/db">
  <http:listener-config name="HTTP_Listener">
    <http:listener-connection host="0.0.0.0" port="8081"/>
  </http:listener-config>
  <db:config name="Database_Config">
    <db:my-sql-connection host="localhost" port="3306" database="mydb" user="root" password="secret"/>
  </db:config>
  <flow name="getUsersFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/users" allowedMethods="GET"/>
    <db:select config-ref="Database_Config">
      <db:sql>SELECT * FROM users</db:sql>
    </db:select>
    <set-payload value="#[payload]" mimeType="application/json"/>
  </flow>
  <flow name="createUserFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/users" allowedMethods="POST"/>
    <db:insert config-ref="Database_Config">
      <db:sql>INSERT INTO users (name, email) VALUES (:name, :email)</db:sql>
    </db:insert>
    <set-payload value='{"status": "created"}' mimeType="application/json"/>
  </flow>
  <flow name="getOrdersFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders" allowedMethods="GET"/>
    <db:select config-ref="Database_Config">
      <db:sql>SELECT * FROM orders</db:sql>
    </db:select>
    <set-payload value="#[payload]" mimeType="application/json"/>
  </flow>
  <flow name="createOrderFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders" allowedMethods="POST"/>
    <db:insert config-ref="Database_Config">
      <db:sql>INSERT INTO orders (user_id, product, amount) VALUES (:userId, :product, :amount)</db:sql>
    </db:insert>
    <set-payload value='{"status": "order_created"}' mimeType="application/json"/>
  </flow>
</mule>`,
};

export default function XmlEditor({ value, onChange, readOnly }: XmlEditorProps) {
  const [sampleOpen, setSampleOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [value]);

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex items-center gap-2">
          <FileCode2 className="h-4 w-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            MuleSoft XML Configuration
          </span>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            (supports multiple XMLs — separate with &lt;?xml declarations)
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="btn-ghost px-2 py-1 text-xs"
            title="Copy to clipboard"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-green-500" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>

          {!readOnly && (
            <div className="relative">
              <button
                onClick={() => setSampleOpen(!sampleOpen)}
                className="btn-secondary px-3 py-1 text-xs"
              >
                Load Sample
                <ChevronDown className="h-3.5 w-3.5" />
              </button>

              {sampleOpen && (
                <div className="absolute right-0 top-full z-10 mt-1 w-64 rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-700 dark:bg-gray-800">
                  {Object.keys(SAMPLE_XMLS).map((name) => (
                    <button
                      key={name}
                      onClick={() => {
                        onChange(SAMPLE_XMLS[name]);
                        setSampleOpen(false);
                      }}
                      className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700"
                    >
                      {name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Editor */}
      <div className="h-[400px]">
        <Editor
          height="100%"
          language="xml"
          value={value}
          onChange={(val) => onChange(val || "")}
          theme="vs-dark"
          options={{
            readOnly,
            minimap: { enabled: false },
            fontSize: 13,
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            automaticLayout: true,
            tabSize: 2,
            padding: { top: 8 },
          }}
        />
      </div>
    </div>
  );
}
